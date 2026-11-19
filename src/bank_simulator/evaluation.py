"""Offline measurements and human review packets for saved AI evaluations."""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from .models import CoachFeedback, InterviewSession
from .services.content_service import ContentService


REVIEW_DIMENSIONS = {
    "client_realism": "Natural customer language, relevant length, and a consistent personality.",
    "client_disclosure": "Requested details are answered without unrelated private facts being volunteered.",
    "client_financial_consistency": "Figures and financial constraints agree with the case and previous replies.",
    "client_memory": "References and contextual follow-ups are resolved or clarified appropriately.",
    "client_product_discussion": "Product reactions use catalogue terms and relevant customer concerns.",
    "coach_discovered_needs": "Fully and partially discovered needs are credited accurately.",
    "coach_missed_needs": "Significant missed needs are identified without falsely marking known facts missing.",
    "coach_product_suitability": "Actual selections, acknowledged limitations, and optional alternatives are judged fairly.",
    "coach_evidence": "Claims are supported by transcript, submission, predefined needs, or catalogue limitations.",
    "coach_usefulness": "Feedback is clear, constructive, prioritized, and gives practical next questions.",
    "coach_conciseness": "Feedback is focused, avoids repeated critique, and uses extra detail only where needed.",
}
REVIEW_SCALE = {
    "1": "Major failures undermine the exercise.",
    "2": "Important errors or omissions require substantial correction.",
    "3": "Usable, with noticeable issues that affect learning.",
    "4": "Accurate and useful, with only minor issues.",
    "5": "Consistently convincing, grounded, and useful throughout.",
}


class HumanRatings(BaseModel):
    """Scores are accepted only as explicit operator-supplied review data."""

    model_config = ConfigDict(extra="forbid")
    reviewer: str | None = None
    scores: dict[str, Annotated[int, Field(strict=True, ge=1, le=5)] | None] = Field(default_factory=dict)
    applicable: dict[str, StrictBool | None] = Field(default_factory=dict)
    evidence: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_criteria(self) -> Self:
        for mapping in (self.scores, self.applicable, self.evidence):
            if set(mapping) - set(REVIEW_DIMENSIONS):
                raise ValueError("Use the documented eleven review criterion IDs.")
        for criterion, score in self.scores.items():
            if score is not None and self.applicable.get(criterion) is False:
                raise ValueError("An inapplicable criterion must remain unscored.")
        return self


def new_manual_review() -> dict:
    return {
        "dimensions": REVIEW_DIMENSIONS.copy(), "scale": REVIEW_SCALE.copy(), "target": 4,
        "scores": dict.fromkeys(REVIEW_DIMENSIONS), "applicable": dict.fromkeys(REVIEW_DIMENSIONS),
        "evidence": dict.fromkeys(REVIEW_DIMENSIONS, ""), "reviewer": None, "reviewed_at": None,
    }


def review_status(review: dict) -> str:
    scores = review.get("scores", {})
    applicable = review.get("applicable", {})
    active = [criterion for criterion in REVIEW_DIMENSIONS if applicable.get(criterion) is not False]
    if not active:
        return "no_applicable_scores"
    values = [scores.get(criterion) for criterion in active]
    if any(value is not None and value < 4 for value in values):
        return "needs_human_attention"
    if all(value is None for value in values):
        return "unscored"
    if any(value is None for value in values):
        return "incomplete"
    return "meets_human_rating_target"


def apply_human_ratings(report: dict, ratings: HumanRatings) -> dict:
    result = deepcopy(report)
    review = new_manual_review()
    previous = report.get("manual_review", {})
    for field in ("scores", "applicable", "evidence"):
        review[field].update({key: value for key, value in previous.get(field, {}).items() if key in REVIEW_DIMENSIONS})
        review[field].update(getattr(ratings, field))
    # Validate merged applicability and scores as well as the incoming changes.
    HumanRatings(scores=review["scores"], applicable=review["applicable"], evidence=review["evidence"])
    review["reviewer"] = ratings.reviewer or previous.get("reviewer")
    review["reviewed_at"] = datetime.now(UTC).isoformat()
    result["manual_review"] = review
    result["manual_review_status"] = review_status(review)
    return result


def feedback_metrics(feedback: CoachFeedback) -> dict:
    sections = feedback.model_dump(mode="json")
    points = [point for section in sections.values() for point in section]
    normalized = [" ".join(point.casefold().split()) for point in points]
    word_count = sum(len(point.split()) for point in points)
    return {
        "word_count": word_count, "soft_word_target": [180, 260],
        "within_soft_word_target": 180 <= word_count <= 260,
        "section_point_counts": {section: len(values) for section, values in sections.items()},
        "exact_duplicate_points": len(normalized) - len(set(normalized)),
        "human_accuracy_review_required": True,
    }


def render_review_packet(report: dict, content: ContentService) -> str:
    """Render transcript evidence and private benchmarks for the reviewer only."""
    session = InterviewSession.model_validate(report["session"])
    if session.client_id is None:
        raise ValueError("The review needs a selected client.")
    profile, needs = content.get_private_client(session.client_id)
    review = report.get("manual_review", new_manual_review())
    lines = [
        f"# Human review of {report.get('scenario_id', profile.id)}", "",
        f"Client — {profile.name}", "", f"Workflow status — {report.get('status', 'unknown')}", "",
        f"Human ratings — {review_status(review)}. Target at least 4/5 in each applicable area.", "",
        "Record scores and cite message numbers below. Mark a criterion inapplicable only with an explanation.", "",
        "| Criterion | Score or N/A | Evidence and notes |", "| --- | --- | --- |",
    ]
    for criterion, description in REVIEW_DIMENSIONS.items():
        score = review.get("scores", {}).get(criterion)
        shown = "N/A" if review.get("applicable", {}).get(criterion) is False else str(score or "Unscored")
        evidence = review.get("evidence", {}).get(criterion, "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {criterion} — {description} | {shown} | {evidence} |")
    lines.extend(["", "## Scoring anchors", ""])
    lines.extend(f"- {score}/5 — {description}" for score, description in REVIEW_SCALE.items())
    lines.extend(["", "## Transcript", ""])
    for index, message in enumerate(session.transcript, 1):
        lines.extend([f"### Message {index} — {message.role.value}", "", "> " + message.content.replace("\n", "\n> "), ""])
    lines.extend(["## Student submission", "", session.student_summary or "Summary not submitted.", ""])
    for choice in session.selected_recommendations:
        product = content.get_product(choice.product_id)
        lines.extend([f"### {product.name}", "", choice.justification, "",
                      "Catalogue limitations — " + " ".join(product.limitations), "",
                      "Catalogue eligibility — " + " ".join(product.eligibility_requirements), ""])
    if report.get("feedback") is not None:
        feedback = CoachFeedback.model_validate(report["feedback"])
        lines.extend(["## Genuine coach feedback", "", f"Feedback length — {feedback_metrics(feedback)['word_count']} words.", ""])
        for heading, values in zip(("What went well", "What was missed", "How to improve"), feedback.model_dump().values()):
            lines.extend([f"### {heading}", "", *(f"- {value}" for value in values), ""])
    lines.extend(["## Private reviewer reference", "",
                  "Use these predefined needs as a benchmark. For each, record fully discovered, partially discovered, or missed and cite transcript evidence.", ""])
    for section in (needs.private_financial_facts, needs.financial_concerns, needs.important_constraints,
                    needs.banking_preferences, needs.hidden_needs):
        lines.extend(f"- [ ] {fact}" for fact in section)
    lines.extend(["", "## Request accounting", "",
                  f"Requests attempted — {report.get('api_calls', 'unknown')}", "",
                  f"Reported token usage — {report.get('token_usage', {})}", ""])
    return "\n".join(lines)
