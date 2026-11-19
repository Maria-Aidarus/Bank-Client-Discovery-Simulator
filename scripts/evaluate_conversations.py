"""Run one explicitly selected live behavior scenario for human review."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from bank_simulator.agents.api_adapter import AIServiceError, OllamaCloudAdapter
from bank_simulator.agents.client_agent import OllamaClientAgent
from bank_simulator.agents.coach_agent import OllamaCoachAgent
from bank_simulator.models import Identifier, OriginalText, ProductRecommendation
from bank_simulator.services.ai_workflow import AIWorkflow
from bank_simulator.services.content_service import ContentService
from bank_simulator.services.interview_service import InterviewService
from bank_simulator.services.recommendation_service import RecommendationService


SCENARIO_FILE = Path(__file__).with_name("conversation_scenarios.json")
REVIEW_DIMENSIONS = {
    "conversational_realism": "Natural customer language, relevant length, and consistent personality.",
    "gradual_disclosure": "Answers requested details without volunteering unrelated facts.",
    "financial_consistency": "Figures and constraints agree with the scenario and earlier answers.",
    "contextual_follow_ups": "Resolves references and asks clarification only when needed.",
    "coaching_accuracy": "Credits actual discoveries and prioritizes genuine gaps fairly.",
    "product_reasoning": "Grounds product discussions and feedback in catalogue features and constraints.",
}
REVIEW_SCALE = {
    "1": "Frequent serious failures.", "2": "Substantial issues requiring correction.",
    "3": "Usable with noticeable lapses.", "4": "Consistent with minor issues.",
    "5": "Convincing, accurate, and well grounded throughout.",
}


class EvaluationScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: Identifier
    client_id: Identifier
    description: OriginalText
    questions: tuple[OriginalText, ...] = Field(min_length=1)
    summary: OriginalText
    recommendations: tuple[ProductRecommendation, ...] = Field(min_length=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Opt in to real Ollama Cloud requests.")
    parser.add_argument("--scenario", help="Run a single scenario ID. Omit to list available cases.")
    parser.add_argument("--output", type=Path, help="Save genuine results and an unscored human-review rubric.")
    args = parser.parse_args()
    cases = [EvaluationScenario.model_validate(record) for record in json.loads(SCENARIO_FILE.read_text())]
    scenarios = {scenario.id: scenario for scenario in cases}
    if len(scenarios) != len(cases):
        parser.error("Scenario IDs must be unique.")
    if args.scenario is None:
        for scenario in cases:
            print(f"{scenario.id} — {scenario.description}")
        return 0
    if not args.live:
        parser.error("Pass --live to opt in to real Ollama Cloud requests.")
    if args.scenario not in scenarios:
        parser.error("Select a listed scenario ID.")
    scenario = scenarios[args.scenario]
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
        "recorded_at": datetime.now(UTC).isoformat(),
        "interview_source": "live_ollama_cloud", "student_submission_source": "script_authored",
        "manual_review": {"dimensions": REVIEW_DIMENSIONS, "scale": REVIEW_SCALE,
                          "scores": {dimension: None for dimension in REVIEW_DIMENSIONS}, "notes": ""},
    }
    try:
        for question in scenario.questions:
            session = workflow.send_student_message(session, question)
            print(f"Student: {question}\nClient: {session.transcript[-1].content}\n")
        session = interviews.end_interview(session)
        session = recommendations.submit_summary(session, scenario.summary)
        session = recommendations.submit_recommendations(session, scenario.recommendations)
        feedback = workflow.generate_feedback(session)
        report.update(status="completed", feedback=feedback.model_dump(mode="json"))
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
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"API requests attempted: {adapter.request_count}")
        print("Reported token usage: " + json.dumps(adapter.token_usage))


if __name__ == "__main__":
    raise SystemExit(main())
