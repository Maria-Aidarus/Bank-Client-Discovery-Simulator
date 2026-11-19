"""Connect agents to existing services while keeping all state caller-owned."""

from ..agents.interfaces import AIClientAgent, AICoachAgent
from ..models import CoachFeedback, InterviewSession, MessageRole
from .coaching_context import build_coaching_context
from .content_service import ContentService
from .interview_service import InterviewService


class AIWorkflow:
    """Application entry points for a full turn and post-submission feedback."""

    def __init__(self, content: ContentService, client_agent: AIClientAgent, coach_agent: AICoachAgent) -> None:
        self._content = content
        self._interviews = InterviewService(content)
        self._client_agent = client_agent
        self._coach_agent = coach_agent

    def send_student_message(self, session: InterviewSession, message: str) -> InterviewSession:
        """Return a complete turn. On failure the original snapshot stays unchanged."""
        if session.transcript and session.transcript[-1].role is MessageRole.STUDENT:
            raise ValueError("Respond to the pending student message before adding another.")
        pending = self._interviews.record_student_message(session, message)
        return self.respond_to_pending(pending)

    def respond_to_pending(self, session: InterviewSession) -> InterviewSession:
        """Use this entry point when the UI already recorded a student message."""
        context = self._interviews.build_client_context(session)
        if not context.transcript or context.transcript[-1].role is not MessageRole.STUDENT:
            raise ValueError("There is no pending student message to answer.")
        reply = self._client_agent.respond(context)
        return self._interviews.record_client_response(session, reply)

    def generate_feedback(self, session: InterviewSession) -> CoachFeedback:
        context = build_coaching_context(session, self._content)
        return CoachFeedback.model_validate(self._coach_agent.evaluate(context))
