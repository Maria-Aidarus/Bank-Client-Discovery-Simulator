"""Validate and store the student's post-interview submissions."""

from collections.abc import Sequence

from ..models import InterviewSession, InterviewStatus, ProductRecommendation
from .content_service import ContentService


class RecommendationService:
    def __init__(self, content: ContentService) -> None:
        self._content = content

    def submit_summary(self, session: InterviewSession, summary: str | None) -> InterviewSession:
        self._require_completed(session)
        if summary is None:
            raise ValueError("Provide a needs summary.")
        return session.validated_update(student_summary=summary)

    def submit_recommendations(
        self, session: InterviewSession, recommendations: Sequence[ProductRecommendation]
    ) -> InterviewSession:
        self._require_completed(session)
        if session.student_summary is None:
            raise ValueError("Submit a needs summary before recommending products.")
        if not recommendations:
            raise ValueError("Select at least one product and provide a justification.")

        updated_session = session.validated_update(selected_recommendations=recommendations)
        for recommendation in updated_session.selected_recommendations:
            self._content.get_product(recommendation.product_id)
        return updated_session

    @staticmethod
    def _require_completed(session: InterviewSession) -> None:
        if session.status is not InterviewStatus.COMPLETED:
            raise ValueError("End the interview before submitting student work.")
