"""Typed integration points for client and coach implementations."""

from typing import Protocol

from ..models import CoachFeedback, CoachingContext, InterviewContext


class AIClientAgent(Protocol):
    def respond(self, context: InterviewContext) -> str:
        """Return the client's next message using the server-side interview context."""
        ...


class AICoachAgent(Protocol):
    def evaluate(self, context: CoachingContext) -> CoachFeedback:
        """Return structured feedback on the interview and recommendations."""
        ...
