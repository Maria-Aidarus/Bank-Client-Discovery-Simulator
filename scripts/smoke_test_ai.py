"""Explicit live integration check. Run with --live to authorize cloud API usage."""

import argparse
import json
import re
from pathlib import Path

from bank_simulator.agents.api_adapter import AIServiceError, OllamaCloudAdapter
from bank_simulator.agents.client_agent import OllamaClientAgent
from bank_simulator.agents.coach_agent import OllamaCoachAgent
from bank_simulator.config import load_settings
from bank_simulator.models import ProductRecommendation
from bank_simulator.services.ai_workflow import AIWorkflow
from bank_simulator.services.content_service import ContentService
from bank_simulator.services.interview_service import InterviewService
from bank_simulator.services.recommendation_service import RecommendationService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Make real, potentially billable API calls.")
    parser.add_argument("--output", type=Path, help="Optionally save the genuine interview and feedback as JSON.")
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to opt in to real Ollama Cloud requests.")

    try:
        # Zero transport retries keeps this check short. Coach repair is bounded to one.
        adapter = OllamaCloudAdapter(load_settings(), max_retries=0)
    except ValueError:
        print("Configuration is incomplete. Check AI_API_URL, AI_API_KEY, and AI_MODEL.")
        return 1

    try:
        content = ContentService()
        interviews = InterviewService(content)
        recommendations = RecommendationService(content)
        workflow = AIWorkflow(content, OllamaClientAgent(adapter), OllamaCoachAgent(adapter))
        session = interviews.create_session("maryam")
        questions = (
            "Hello, could you tell me a little about your business?",
            "How do customer payment delays affect your ability to pay suppliers? "
            "How much business cash is available and what payments are due soon?",
            "Are there any restrictions or preferences regarding the financing arrangements you would accept?",
        )
        replies = []
        for question in questions:
            session = workflow.send_student_message(session, question)
            replies.append(session.transcript[-1].content)
            print(f"Student: {question}\nClient: {replies[-1]}\n")
        session = interviews.end_interview(session)
        summary = (
            "Maryam needs to manage the timing gap between customer receipts and business payments. "
            "Confirm amounts and dates from the interview and investigate Sharia-compliant options."
        )
        session = recommendations.submit_summary(session, summary)
        session = recommendations.submit_recommendations(session, [ProductRecommendation(
            product_id="business-cash-management",
            justification="Track collections and upcoming payments. This service supplies no financing.",
        )])
        feedback = workflow.generate_feedback(session)
        print("AI Coach feedback\n" + feedback.model_dump_json(indent=2))

        # These are narrow signals for manual review, not a semantic grading model.
        cash_reply = replies[1].lower().replace(",", "")
        behavior = {
            "intro_keeps_private_cash_and_preferences_out": not re.search(
                r"\b(?:25000|40000|15000|sharia|islamic)\b", replies[0].lower().replace(",", "")
            ),
            "working_capital_reply_mentions_expected_amounts": "25000" in cash_reply and "40000" in cash_reply,
            "preference_reply_mentions_sharia": bool(re.search(r"sharia|islamic", replies[2], re.IGNORECASE)),
            "all_feedback_sections_have_content": all(feedback.model_dump().values()),
        }
        print("Connectivity: successful. All three client turns and coach feedback were received.")
        print("Behavioral checks (manual review also required): " + json.dumps(behavior))
        report = {
            "configured_model": adapter.model,
            "response_models": sorted(adapter.response_models),
            "api_calls": adapter.request_count,
            "behavioral_checks": behavior,
            "session": session.model_dump(mode="json"),
            "feedback": feedback.model_dump(mode="json"),
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0 if all(behavior.values()) else 2
    except AIServiceError as exc:
        print(f"Live test failed: {exc}")
        return 1
    finally:
        print(f"Configured model: {adapter.model}")
        print(f"API response models: {', '.join(sorted(adapter.response_models)) or 'unconfirmed'}")
        print(f"API calls attempted (including repair): {adapter.request_count}")
        adapter.close()


if __name__ == "__main__":
    raise SystemExit(main())
