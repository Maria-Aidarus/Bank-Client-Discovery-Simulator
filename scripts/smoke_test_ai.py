"""Explicit live integration check. Run with --live to authorize cloud API usage."""

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from bank_simulator.agents.api_adapter import AIServiceError, OllamaCloudAdapter
from bank_simulator.agents.client_agent import OllamaClientAgent
from bank_simulator.agents.coach_agent import OllamaCoachAgent
from bank_simulator.config import load_settings
from bank_simulator.models import InterviewSession, ProductRecommendation
from bank_simulator.services.ai_workflow import AIWorkflow
from bank_simulator.services.coaching_context import build_coaching_context
from bank_simulator.services.content_service import ContentService
from bank_simulator.services.interview_service import InterviewService
from bank_simulator.services.recommendation_service import RecommendationService


def _write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Make real, potentially billable API calls.")
    parser.add_argument("--output", type=Path, help="Optionally save the genuine interview and feedback as JSON.")
    parser.add_argument("--coach-only", type=Path, help="Load a saved interview and call only the coach.")
    parser.add_argument("--diagnostics", type=Path, help="Write safe response metadata and validation categories.")
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to opt in to real Ollama Cloud requests.")

    paths = [path.resolve() for path in (args.output, args.diagnostics, args.coach_only) if path]
    if len(paths) != len(set(paths)):
        parser.error("Input, output, and diagnostic paths must be different.")
    content = ContentService()
    saved_session = None
    if args.coach_only:
        try:
            payload = json.loads(args.coach_only.read_text(encoding="utf-8"))
            saved_session = InterviewSession.model_validate(payload["session"] if "session" in payload else payload)
            build_coaching_context(saved_session, content)
        except (OSError, ValueError, KeyError, TypeError):
            print("Saved interview is unreadable or invalid for coaching. No API calls were made.")
            return 1
    events: list[dict[str, object]] = []
    sink = events.append if args.diagnostics else None
    try:
        # Transport retries are disabled. Coach generation has one recovery allowance.
        adapter = OllamaCloudAdapter(load_settings(), max_retries=0, diagnostics=sink)
    except ValueError:
        print("Configuration is incomplete. Check AI_API_URL, AI_API_KEY, and AI_MODEL.")
        return 1

    report: dict[str, object] = {
        "status": "failed", "mode": "coach_only" if args.coach_only else "full",
        "recorded_at": datetime.now(UTC).isoformat(),
        "interview_source": "saved_input" if args.coach_only else "live_ollama_cloud",
        "student_submission_source": "saved_input" if args.coach_only else "script_authored",
    }
    session = saved_session
    try:
        interviews = InterviewService(content)
        recommendations = RecommendationService(content)
        workflow = AIWorkflow(content, OllamaClientAgent(adapter), OllamaCoachAgent(adapter, diagnostics=sink))
        if session is None:
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

        behavior = {"all_feedback_sections_have_content": all(feedback.model_dump().values())}
        if not args.coach_only:
            # These are narrow signals for manual review, not a semantic grading model.
            cash_reply = replies[1].lower().replace(",", "")
            behavior.update({
                "intro_keeps_private_cash_and_preferences_out": not re.search(
                    r"\b(?:25000|40000|15000|sharia|islamic)\b", replies[0].lower().replace(",", "")
                ),
                "working_capital_reply_mentions_expected_amounts": "25000" in cash_reply and "40000" in cash_reply,
                "preference_reply_mentions_sharia": bool(re.search(r"sharia|islamic", replies[2], re.IGNORECASE)),
            })
        print("Connectivity: successful. Validated coach feedback was received.")
        print("Behavioral checks (manual review also required): " + json.dumps(behavior))
        report.update({
            "status": "passed" if all(behavior.values()) else "behavior_review_required",
            "behavioral_checks": behavior, "feedback": feedback.model_dump(mode="json"),
        })
        return 0 if all(behavior.values()) else 2
    except AIServiceError as exc:
        report["failure_category"] = exc.category
        print(f"Live test failed: {exc}")
        return 1
    finally:
        report.update({
            "configured_model": adapter.model, "response_models": sorted(adapter.response_models),
            "api_calls": adapter.request_count,
            "token_usage": adapter.token_usage,
            "connectivity": "confirmed" if adapter.response_models else "unconfirmed",
            "session": session.model_dump(mode="json") if session else None,
        })
        adapter.close()
        if args.output:
            _write_report(args.output, report)
        if args.diagnostics:
            _write_report(args.diagnostics, {
                "status": report["status"], "mode": report["mode"],
                "configured_model": adapter.model, "api_calls": adapter.request_count,
                "token_usage": adapter.token_usage,
                "events": events,
            })
        print(f"Configured model: {adapter.model}")
        print(f"API response models: {', '.join(sorted(adapter.response_models)) or 'unconfirmed'}")
        print(f"API calls attempted (including repair): {adapter.request_count}")
        print("Reported token usage: " + json.dumps(adapter.token_usage))


if __name__ == "__main__":
    raise SystemExit(main())
