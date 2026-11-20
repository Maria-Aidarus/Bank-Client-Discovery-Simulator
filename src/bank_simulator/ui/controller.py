"""Caller-owned web state and bounded actions, independent of Streamlit rendering."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
import logging
from typing import TypeVar

from openai.types.chat import ChatCompletionMessageParam

from ..agents.api_adapter import AIServiceError, ChatAdapter, OllamaCloudAdapter
from ..agents.client_agent import OllamaClientAgent
from ..agents.coach_agent import OllamaCoachAgent
from ..models import CoachFeedback, InterviewSession, InterviewStatus, MessageRole, ProductRecommendation
from ..services.ai_workflow import AIWorkflow
from ..services.content_service import ContentService
from ..services.interview_service import InterviewService
from ..services.recommendation_service import RecommendationService


MAX_QUESTIONS = 30
MAX_REQUESTS = 40
COACH_REQUEST_RESERVE = 2
MAX_MESSAGE_CHARS = 2000
MAX_SUMMARY_CHARS = 8000
MAX_JUSTIFICATION_CHARS = 4000
T = TypeVar("T")
_LOGGER = logging.getLogger(__name__)


@dataclass
class Workspace:
    """One browser's UI state. Backend models are replaced, never mutated."""

    session: InterviewSession | None = None
    feedback: CoachFeedback | None = None
    failed_question: str | None = None
    error: str | None = None
    requests: int = 0
    busy: bool = False
    editing: bool = False
    justification_drafts: dict[str, str] = field(default_factory=dict)

    @property
    def stage(self) -> int:
        if self.session is None:
            return 1
        if self.session.status is InterviewStatus.ACTIVE:
            return 2
        return 4 if self.session.selected_recommendations and not self.editing else 3

    @property
    def question_count(self) -> int:
        return sum(message.role is MessageRole.STUDENT for message in self.session.transcript) if self.session else 0

    @property
    def can_send(self) -> bool:
        return (self.session is not None and self.session.status is InterviewStatus.ACTIVE
                and not self.busy and self.question_count < MAX_QUESTIONS
                and self.requests < MAX_REQUESTS - COACH_REQUEST_RESERVE)


class _BudgetedAdapter:
    """Count every generation, including the Coach's single recovery request."""

    def __init__(self, adapter: ChatAdapter, state: Workspace) -> None:
        self._adapter = adapter
        self._state = state

    def complete(
        self, messages: Sequence[ChatCompletionMessageParam], *, max_tokens: int = 2048,
        temperature: float = 0.3, json_mode: bool = False,
    ) -> str:
        if self._state.requests >= MAX_REQUESTS:
            raise AIServiceError("This interview has reached its AI request limit.", category="request_limit")
        self._state.requests += 1
        return self._adapter.complete(messages, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode)


def _log_request_failure(metadata: dict[str, object]) -> None:
    """Allowlist failure timing for Cloud logs; never log the response or context."""
    category = metadata.get("validation_failure_category")
    if category not in {"timeout", "connection", "http_error", "invalid_api_response",
                        "truncated", "reasoning_only", "empty_content", "missing_choices",
                        "unsupported_finish", "unsupported_content", "sensitive_content"}:
        return
    elapsed = metadata.get("elapsed_seconds")
    status = metadata.get("http_status")
    phase = metadata.get("timeout_phase")
    _LOGGER.warning(
        "AI request failed: category=%s elapsed_seconds=%s http_status=%s timeout_phase=%s",
        category, elapsed if type(elapsed) in (float, int) else None,
        status if type(status) is int else None,
        phase if phase in {"ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout", "unknown"} else None,
    )


def create_adapter() -> OllamaCloudAdapter:
    """Open a short-lived connection only for an explicit student action."""
    return OllamaCloudAdapter(max_retries=0, diagnostics=_log_request_failure)


class WebController:
    """Translate explicit UI actions into existing service calls."""

    def __init__(self, state: Workspace, content: ContentService) -> None:
        self.state = state
        self.content = content
        self.interviews = InterviewService(content)

    def start(self, client_id: str) -> None:
        if self.state.busy:
            return
        session = self.interviews.create_session(client_id)
        self.state.session = session
        self.state.feedback = None
        self.state.failed_question = None
        self.state.error = None
        self.state.requests = 0
        self.state.editing = False
        self.state.justification_drafts.clear()

    def choose_another(self) -> None:
        if not self.state.busy:
            self.state.session = None
            self.state.feedback = None
            self.state.failed_question = None
            self.state.error = None
            self.state.requests = 0
            self.state.editing = False
            self.state.justification_drafts.clear()

    def send(self, message: str) -> bool:
        if self.state.busy:
            return False
        session = self.state.session
        if session is None or not self.state.can_send:
            self.state.error = "The interview limit has been reached. You can still end the interview and submit your work."
            return False
        if not message.strip() or len(message) > MAX_MESSAGE_CHARS:
            self.state.error = f"Enter a question of 1–{MAX_MESSAGE_CHARS:,} characters."
            return False
        self.state.failed_question = message
        updated = self._run(lambda workflow: workflow.send_student_message(session, message))
        if updated is None:
            return False
        self.state.session = updated
        self.state.failed_question = None
        return True

    def end(self) -> None:
        if self.state.busy or self.state.session is None:
            return
        self.state.session = self.interviews.end_interview(self.state.session)
        self.state.failed_question = None
        self.state.error = None

    def submit(self, summary: str, choices: list[ProductRecommendation]) -> None:
        """Commit both parts atomically, preserving the student's original strings."""
        if self.state.busy or self.state.session is None:
            raise ValueError("End an interview before submitting your work.")
        if len(summary) > MAX_SUMMARY_CHARS:
            raise ValueError("The needs summary is too long.")
        if any(len(choice.justification) > MAX_JUSTIFICATION_CHARS for choice in choices):
            raise ValueError("A product justification is too long.")
        recommendations = RecommendationService(self.content)
        candidate = recommendations.submit_summary(self.state.session, summary)
        candidate = recommendations.submit_recommendations(candidate, choices)
        self.state.session = candidate
        self.state.feedback = None
        self.state.error = None
        self.state.editing = False

    def coach(self) -> bool:
        if self.state.feedback is not None or self.state.busy:
            return False
        session = self.state.session
        if session is None or not session.selected_recommendations:
            raise ValueError("Submit your needs summary and recommendations before requesting feedback.")
        if self.state.requests >= MAX_REQUESTS:
            self.state.error = "This interview has reached its AI request limit. Your interview and submission can still be downloaded."
            return False
        feedback = self._run(lambda workflow: workflow.generate_feedback(session))
        if feedback is None:
            return False
        self.state.feedback = feedback
        return True

    def revise(self) -> None:
        if self.state.busy or self.state.session is None:
            return
        self.state.feedback = None
        self.state.error = None
        self.state.editing = True

    def _run(self, action: Callable[[AIWorkflow], T]) -> T | None:
        if self.state.busy:
            return None
        self.state.busy = True
        self.state.error = None
        adapter = None
        try:
            adapter = create_adapter()
            budget = _BudgetedAdapter(adapter, self.state)
            workflow = AIWorkflow(self.content, OllamaClientAgent(budget), OllamaCoachAgent(budget))
            return action(workflow)
        except AIServiceError as exc:
            # Adapter errors are sanitized; raw SDK exceptions are never rendered.
            self.state.error = str(exc)
        except ValueError:
            self.state.error = "The AI connection could not be initialized. Check the server's AI configuration. Your saved work is unchanged."
        except Exception:
            self.state.error = "The AI request could not be completed. Your saved work is unchanged. Please retry."
        finally:
            if adapter is not None:
                try:
                    adapter.close()
                except Exception:
                    # Connection cleanup must not leak raw SDK errors into the page.
                    pass
            self.state.busy = False
        return None
