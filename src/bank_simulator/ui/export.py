"""Allowlisted student report export. Never serialize agent or reviewer contexts."""

import json

from ..models import CoachFeedback, InterviewSession
from ..services.content_service import ContentService


def student_report(session: InterviewSession, feedback: CoachFeedback | None, content: ContentService) -> str:
    """Return public identity, observed dialogue, original submission, and final feedback."""
    if session.client_id is None:
        raise ValueError("Select a client before exporting an interview.")
    report = {
        "report_type": "student_interview",
        "session_id": str(session.session_id),
        "status": session.status.value,
        "client": content.get_client(session.client_id).model_dump(mode="json"),
        "transcript": [message.model_dump(mode="json") for message in session.transcript],
        "student_summary": session.student_summary,
        "recommendations": [
            {"product_id": choice.product_id, "product_name": content.get_product(choice.product_id).name,
             "justification": choice.justification}
            for choice in session.selected_recommendations
        ],
        "coach_feedback": feedback.model_dump(mode="json") if feedback else None,
    }
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"
