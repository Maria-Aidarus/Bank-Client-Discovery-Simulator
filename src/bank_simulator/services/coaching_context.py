"""Assemble the server-side input for the coaching agent."""

from ..models import CoachingContext, InterviewSession, InterviewStatus
from .content_service import ContentService


def build_coaching_context(session: InterviewSession, content: ContentService) -> CoachingContext:
    """Collect validated interview and catalogue data after student submission."""
    if session.status is not InterviewStatus.COMPLETED or session.client_id is None:
        raise ValueError("End the interview before building coaching context.")
    if session.student_summary is None or not session.selected_recommendations:
        raise ValueError("Submit a needs summary and product recommendations before requesting coaching.")

    profile, needs = content.get_private_client(session.client_id)
    return CoachingContext(
        client_profile=profile,
        hidden_needs=needs,
        transcript=session.transcript,
        products=content.list_products(),
        student_summary=session.student_summary,
        recommendations=session.selected_recommendations,
    )
