"""Conduct a live terminal interview through the existing backend services."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from bank_simulator.agents.api_adapter import AIServiceError, OllamaCloudAdapter
from bank_simulator.agents.client_agent import OllamaClientAgent
from bank_simulator.agents.coach_agent import OllamaCoachAgent
from bank_simulator.models import ProductRecommendation
from bank_simulator.services.ai_workflow import AIWorkflow
from bank_simulator.services.content_service import ContentService
from bank_simulator.services.interview_service import InterviewService
from bank_simulator.services.recommendation_service import RecommendationService


def _nonblank(prompt: str) -> str:
    while True:
        value = input(prompt)
        if value.strip():
            return value
        print("Please enter some text.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Opt in to real Ollama Cloud API usage.")
    parser.add_argument("--client", help="Public client ID. Omit to choose interactively.")
    parser.add_argument("--output", type=Path, help="Save the interview and feedback as JSON.")
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to opt in to real Ollama Cloud requests.")

    content = ContentService()
    client_id = args.client
    if client_id is None:
        for client in content.list_clients():
            print(f"{client.id} — {client.name}")
        try:
            client_id = _nonblank("Choose a client ID: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nClient selection stopped.")
            return 1
    try:
        profile = content.get_client(client_id)
    except ValueError as exc:
        print(str(exc))
        return 1
    print(f"\n{profile.name}, {profile.age} — {profile.occupation}\n{profile.background}")
    print(profile.public_financial_situation)
    print(profile.interview_opening_context)
    try:
        adapter = OllamaCloudAdapter(max_retries=0)
    except ValueError:
        print("Set valid AI_API_URL, AI_API_KEY, and AI_MODEL values in the local configuration.")
        return 1

    interviews = InterviewService(content)
    recommendations = RecommendationService(content)
    workflow = AIWorkflow(content, OllamaClientAgent(adapter), OllamaCoachAgent(adapter))
    session = interviews.create_session(profile.id)
    feedback = None
    status = "interrupted"
    try:
        print("\nEnter interview questions. Use /end to finish or /retry after a failed question.")
        pending = None
        while True:
            message = _nonblank("Student: ")
            command = message.strip().lower()
            if command == "/end":
                break
            if command == "/retry":
                if pending is None:
                    print("There is no failed question to retry.")
                    continue
                message = pending
            try:
                updated = workflow.send_student_message(session, message)
            except AIServiceError as exc:
                pending = message
                print(f"AI request failed. {exc}\nUse /retry, enter a new question, or use /end.")
                continue
            session = updated
            pending = None
            print(f"{profile.name}: {session.transcript[-1].content}\n")

        session = interviews.end_interview(session)
        session = recommendations.submit_summary(session, _nonblank("Needs summary: "))
        print("\nFictional product catalogue")
        for product in content.list_products():
            print(f"\n{product.id} — {product.name}\n{product.description}")
            print("Features — " + " ".join(product.key_features))
            print("Limitations — " + " ".join(product.limitations))
            print("Eligibility — " + " ".join(product.eligibility_requirements))
        while True:
            selected = _nonblank("\nProduct IDs (comma-separated): ")
            product_ids = [item.strip() for item in selected.split(",")]
            try:
                if len(set(product_ids)) != len(product_ids):
                    raise ValueError("Choose each product once.")
                for product_id in product_ids:
                    content.get_product(product_id)
            except ValueError as exc:
                print(str(exc))
                continue
            choices = [ProductRecommendation(
                product_id=product_id, justification=_nonblank(f"Justification for {product_id}: "),
            ) for product_id in product_ids]
            session = recommendations.submit_recommendations(session, choices)
            break
        while True:
            try:
                feedback = workflow.generate_feedback(session)
            except AIServiceError as exc:
                print(f"Coaching failed. {exc}")
                if input("Enter /retry to request coaching again, or press Enter to save and stop: ").strip() == "/retry":
                    continue
                status = "coach_failed"
                return 1
            break
        for title, points in (
            ("What went well", feedback.what_went_well),
            ("What was missed", feedback.what_was_missed),
            ("How to improve", feedback.how_to_improve),
        ):
            print(f"\n{title}")
            for point in points:
                print(f"- {point}")
        status = "completed"
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nInterview stopped. Completed turns are available in the optional export.")
        return 1
    finally:
        adapter.close()
        if args.output:
            report = {
                "status": status, "recorded_at": datetime.now(UTC).isoformat(),
                "configured_model": adapter.model, "response_models": sorted(adapter.response_models),
                "api_calls": adapter.request_count, "token_usage": adapter.token_usage,
                "interview_source": "live_ollama_cloud", "student_submission_source": "manual",
                "session": session.model_dump(mode="json"),
                "feedback": feedback.model_dump(mode="json") if feedback else None,
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"API requests attempted: {adapter.request_count}")
        print("Reported token usage: " + json.dumps(adapter.token_usage))


if __name__ == "__main__":
    raise SystemExit(main())
