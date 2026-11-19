"""Manage the interview lifecycle and record messages supplied by callers."""

from datetime import UTC, datetime

from ..models import InterviewContext, InterviewMessage, InterviewSession, InterviewStatus, MessageRole
from .content_service import ContentService


class InterviewService:
    """Return new session snapshots for the caller to store."""

    def __init__(self, content: ContentService) -> None:
        self._content = content

    def create_session(self, client_id: str | None = None) -> InterviewSession:
        """Create a draft or start an interview with an already selected client."""
        session = InterviewSession()
        if client_id is None:
            return session
        return self.select_client(session, client_id)

    def select_client(self, session: InterviewSession, client_id: str) -> InterviewSession:
        if session.status is not InterviewStatus.DRAFT:
            raise ValueError("A client can only be selected for a draft interview.")
        client = self._content.get_client(client_id)
        return session.validated_update(client_id=client.id, status=InterviewStatus.ACTIVE)

    def record_student_message(self, session: InterviewSession, content: str) -> InterviewSession:
        return self._record_message(session, MessageRole.STUDENT, content)

    def record_client_response(self, session: InterviewSession, content: str) -> InterviewSession:
        """Record a response supplied by an external caller or client agent."""
        return self._record_message(session, MessageRole.CLIENT, content)

    def get_history(self, session: InterviewSession) -> tuple[InterviewMessage, ...]:
        return session.transcript

    def end_interview(self, session: InterviewSession) -> InterviewSession:
        self._require_active(session)
        return session.validated_update(status=InterviewStatus.COMPLETED)

    def reset_interview(self, session: InterviewSession) -> InterviewSession:
        """Start a fresh attempt, keeping the selected client if there was one."""
        return self.create_session(session.client_id)

    def build_client_context(self, session: InterviewSession) -> InterviewContext:
        """Package private context for the client agent. Use server-side only."""
        client_id = self._require_active(session)
        profile, needs = self._content.get_private_client(client_id)
        return InterviewContext(client_profile=profile, hidden_needs=needs, transcript=session.transcript)

    def _record_message(
        self, session: InterviewSession, role: MessageRole, content: str
    ) -> InterviewSession:
        self._require_active(session)
        timestamp = datetime.now(UTC)
        if session.transcript:
            timestamp = max(timestamp, session.transcript[-1].timestamp)
        message = InterviewMessage(role=role, content=content, timestamp=timestamp)
        return session.validated_update(transcript=(*session.transcript, message))

    @staticmethod
    def _require_active(session: InterviewSession) -> str:
        if session.status is not InterviewStatus.ACTIVE or session.client_id is None:
            raise ValueError("This action requires an active interview with a selected client.")
        return session.client_id
