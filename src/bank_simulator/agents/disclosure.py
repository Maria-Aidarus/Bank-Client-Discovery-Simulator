"""Determine available private facts using data-authored question patterns."""

import re
from dataclasses import dataclass

from ..models import InterviewContext, MessageRole


_INSTRUCTION_REQUEST = re.compile(
    r"answer\s*key|system\s*(?:prompt|instructions?)|private\s*(?:facts|needs|data)|"
    r"hidden\s*(?:facts|needs|information)|ignore\b.{0,50}\b(?:instructions?|rules)|"
    r"(?:reveal|show|print|list)\b.{0,30}\b(?:secrets|prompts)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DisclosureState:
    """Internal diagnostics. Only facts are passed to the roleplay model."""

    topics: tuple[str, ...]
    facts: tuple[str, ...]


class DisclosureController:
    def available_information(self, context: InterviewContext) -> DisclosureState:
        """Replay student questions to recover unlocks without global session state."""
        questions = []
        for message in context.transcript:
            text = " ".join(message.content.lower().replace("’", "'").split())
            if message.role is MessageRole.STUDENT and not _INSTRUCTION_REQUEST.search(text):
                questions.append(text)

        topics: list[str] = []
        facts: list[str] = []
        for rule in context.hidden_needs.disclosure_topics:
            if any(re.search(pattern, text, re.IGNORECASE) for pattern in rule.question_patterns for text in questions):
                topics.append(rule.topic)
                for reference in rule.fact_references:
                    fact = getattr(context.hidden_needs, reference.section)[reference.index]
                    if fact not in facts:
                        facts.append(fact)
        return DisclosureState(tuple(topics), tuple(facts))
