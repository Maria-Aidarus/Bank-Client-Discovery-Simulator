"""Run one explicitly selected live behavior scenario for human review."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from bank_simulator.agents.api_adapter import AIServiceError, OllamaCloudAdapter
from bank_simulator.agents.client_agent import OllamaClientAgent
from bank_simulator.agents.coach_agent import OllamaCoachAgent
from bank_simulator.evaluation import (
    REVIEW_DIMENSIONS, REVIEW_SCALE, HumanRatings, apply_human_ratings, feedback_metrics,
    new_manual_review, render_review_packet, review_status,
)
from bank_simulator.models import CoachFeedback, Identifier, InterviewSession, OriginalText, ProductRecommendation
from bank_simulator.services.ai_workflow import AIWorkflow
from bank_simulator.services.coaching_context import build_coaching_context
from bank_simulator.services.content_service import ContentService
from bank_simulator.services.interview_service import InterviewService
from bank_simulator.services.recommendation_service import RecommendationService


SCENARIO_FILE = Path(__file__).with_name("conversation_scenarios.json")


class EvaluationScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: Identifier
    client_id: Identifier
    description: OriginalText
    questions: tuple[OriginalText, ...] = Field(min_length=1)
    summary: OriginalText
    recommendations: tuple[ProductRecommendation, ...] = Field(min_length=1)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_review(path: Path, report: dict, content: ContentService) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_review_packet(report, content), encoding="utf-8")


def _coverage(scenarios: dict[str, EvaluationScenario], directory: Path, content: ContentService) -> None:
    recorded: dict[str, list[str]] = {identifier: [] for identifier in scenarios}
    failed: dict[str, list[str]] = {identifier: [] for identifier in scenarios}
    for path in sorted(directory.glob("*.json")):
        try:
            report = json.loads(path.read_text())
            if not isinstance(report, dict):
                continue
            identifier = report.get("scenario_id")
            if identifier not in scenarios:
                continue
            session = InterviewSession.model_validate(report["session"])
            if session.client_id != scenarios[identifier].client_id:
                continue
            questions = tuple(message.content for message in session.transcript if message.role.value == "student")
            expected_questions = scenarios[identifier].questions
            if report.get("status") == "failed" and questions == expected_questions[:len(questions)]:
                failed[identifier].append(path.name)
                continue
            if report.get("status") not in {"completed", "passed"} or questions != expected_questions:
                continue
            build_coaching_context(session, content)
            CoachFeedback.model_validate(report["feedback"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        recorded[identifier].append(path.name)
    for identifier, files in recorded.items():
        status = "recorded: " + ", ".join(files) if files else "pending live execution"
        if failed[identifier]:
            status += " | failed attempts: " + ", ".join(failed[identifier])
        print(f"{identifier} — {status}")
    print("Coverage counts validated workflow records. Human quality ratings require separate review.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Opt in to real Ollama Cloud requests.")
    parser.add_argument("--scenario", help="Run a single scenario ID. Omit to list available cases.")
    parser.add_argument("--output", type=Path, help="Save genuine results and an unscored human-review rubric.")
    parser.add_argument("--review-output", type=Path, help="Write a human-readable reviewer Markdown packet.")
    parser.add_argument("--review-report", type=Path, help="Review a saved report offline without making API calls.")
    parser.add_argument("--ratings", type=Path, help="Apply an explicitly human-supplied ratings JSON file offline.")
    parser.add_argument("--ratings-template", type=Path, help="Write a blank human-ratings template.")
    parser.add_argument("--coverage", action="store_true", help="List recorded and pending scenarios offline.")
    parser.add_argument("--results-dir", type=Path, default=SCENARIO_FILE.parent.parent / "samples")
    args = parser.parse_args()
    cases = [EvaluationScenario.model_validate(record) for record in json.loads(SCENARIO_FILE.read_text())]
    scenarios = {scenario.id: scenario for scenario in cases}
    if len(scenarios) != len(cases):
        parser.error("Scenario IDs must be unique.")
    if (args.ratings or args.ratings_template) and not args.review_report:
        parser.error("Use ratings options with --review-report.")
    if args.review_report:
        if args.scenario or args.live:
            parser.error("Saved-report review runs offline and is a separate mode from --scenario.")
        output = args.output
        if args.ratings and output is None:
            output = args.review_report.with_name(args.review_report.stem + "_reviewed.json")
        review_path = args.review_output or args.review_report.with_name(args.review_report.stem + ".review.md")
        destinations = [path.resolve() for path in (output, review_path, args.ratings_template) if path]
        sources = [path.resolve() for path in (args.review_report, args.ratings) if path]
        if len(destinations) != len(set(destinations)) or set(destinations).intersection(sources):
            parser.error("Review outputs must have distinct paths and preserve the input files.")
        try:
            report = json.loads(args.review_report.read_text())
            content = ContentService()
            # Rendering validates the selected client, session, and any feedback.
            render_review_packet(report, content)
            if args.ratings:
                report = apply_human_ratings(report, HumanRatings.model_validate_json(args.ratings.read_text()))
            if output:
                _write_json(output, report)
            _write_review(review_path, report, content)
            if args.ratings_template:
                template = HumanRatings(
                    scores=dict.fromkeys(REVIEW_DIMENSIONS), applicable=dict.fromkeys(REVIEW_DIMENSIONS),
                    evidence=dict.fromkeys(REVIEW_DIMENSIONS, ""),
                )
                _write_json(args.ratings_template, template.model_dump())
        except (OSError, ValueError, KeyError, TypeError):
            print("The saved report or human ratings could not be validated or written.")
            return 1
        print(f"Human review status — {review_status(report.get('manual_review', new_manual_review()))}")
        print(f"Review packet — {review_path}")
        return 0
    if args.coverage:
        _coverage(scenarios, args.results_dir, ContentService())
        return 0
    if args.scenario is None:
        for scenario in cases:
            requests = len(scenario.questions) + 1
            print(f"{scenario.id} — {requests} requests normally, {requests + 1} maximum — {scenario.description}")
        return 0
    if not args.live:
        parser.error("Pass --live to opt in to real Ollama Cloud requests.")
    if args.scenario not in scenarios:
        parser.error("Select a listed scenario ID.")
    if args.output and args.review_output and args.output.resolve() == args.review_output.resolve():
        parser.error("JSON and human-review output paths must differ.")
    scenario = scenarios[args.scenario]
    planned_requests = len(scenario.questions) + 1
    print(f"Selected {scenario.id} — {planned_requests} requests normally, {planned_requests + 1} maximum.")
    content = ContentService()
    content.get_client(scenario.client_id)
    for choice in scenario.recommendations:
        content.get_product(choice.product_id)
    events = []
    try:
        adapter = OllamaCloudAdapter(max_retries=0, diagnostics=events.append)
    except ValueError:
        print("Local AI configuration is incomplete or invalid.")
        return 1
    interviews = InterviewService(content)
    recommendations = RecommendationService(content)
    workflow = AIWorkflow(content, OllamaClientAgent(adapter), OllamaCoachAgent(adapter, diagnostics=events.append))
    session = interviews.create_session(scenario.client_id)
    report = {
        "status": "failed", "scenario_id": scenario.id,
        "evaluation_version": "2.6", "planned_requests": {"normal": planned_requests, "maximum": planned_requests + 1},
        "recorded_at": datetime.now(UTC).isoformat(),
        "interview_source": "live_ollama_cloud", "student_submission_source": "script_authored",
        "manual_review": new_manual_review(), "manual_review_status": "unscored",
    }
    try:
        for question in scenario.questions:
            session = workflow.send_student_message(session, question)
            print(f"Student: {question}\nClient: {session.transcript[-1].content}\n")
        session = interviews.end_interview(session)
        session = recommendations.submit_summary(session, scenario.summary)
        session = recommendations.submit_recommendations(session, scenario.recommendations)
        feedback = workflow.generate_feedback(session)
        report.update(status="completed", feedback=feedback.model_dump(mode="json"), feedback_metrics=feedback_metrics(feedback))
        print(feedback.model_dump_json(indent=2))
        print("Review the genuine transcript with the 1–5 rubric. Scores have been left blank for a human reviewer.")
        return 0
    except AIServiceError as exc:
        report["failure_category"] = exc.category
        print(f"Live evaluation failed. {exc}")
        return 1
    finally:
        adapter.close()
        report.update(
            configured_model=adapter.model, response_models=sorted(adapter.response_models),
            api_calls=adapter.request_count, token_usage=adapter.token_usage,
            session=session.model_dump(mode="json"), diagnostics=events,
        )
        if args.output:
            _write_json(args.output, report)
        review_path = args.review_output or (args.output.with_name(args.output.stem + ".review.md") if args.output else None)
        if review_path:
            _write_review(review_path, report, content)
        print(f"API requests attempted: {adapter.request_count}")
        print("Reported token usage: " + json.dumps(adapter.token_usage))


if __name__ == "__main__":
    raise SystemExit(main())
