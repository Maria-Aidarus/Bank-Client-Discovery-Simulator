"""Determine available private facts using data-authored question patterns."""

import re
from dataclasses import dataclass

from ..models import BankingProduct, DisclosureTopic, HiddenNeeds, InterviewContext, MessageRole


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
    relevant_facts: tuple[str, ...] = ()
    disclosed_facts: tuple[str, ...] = ()


_FOLLOW_UP = re.compile(
    r"^(?:and\s+)?(?:what about (?:that|it|those)|(?:can|could|would) you (?:explain|elaborate|say more)|"
    r"tell me more|how much (?:is|was) (?:it|that)|when (?:is|was) (?:it|that) due|"
    r"when (?:would|will) (?:that|it) happen|why (?:does|would) (?:that|it) (?:concern|worry|matter)|"
    r"why is (?:that|it) important|would (?:that|it)(?: account| product| facility)? work|does (?:that|it) still apply)",
    re.IGNORECASE,
)


def _matches(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def mentions_product(product: BankingProduct, text: str) -> bool:
    """Match catalogue names and IDs without treating student text as instructions."""
    return any(re.search(r"\b" + re.escape(name) + r"\b", text, re.IGNORECASE)
               for name in (product.name, product.id))


def _facts(needs: HiddenNeeds, rules: tuple[DisclosureTopic, ...], selected: set[int]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        getattr(needs, reference.section)[reference.index]
        for index, rule in enumerate(rules) if index in selected for reference in rule.fact_references
    ))


class DisclosureController:
    def available_information(self, context: InterviewContext) -> DisclosureState:
        """Replay student questions to recover unlocks without global session state."""
        rules = context.hidden_needs.disclosure_topics
        available: set[int] = set()
        disclosed: set[int] = set()
        focus: set[int] = set()
        relevant: set[int] = set()
        for message in context.transcript:
            text = " ".join(message.content.lower().replace("’", "'").split())
            if message.role is MessageRole.CLIENT:
                spoken = {index for index in available if _matches(rules[index].response_patterns, text)}
                disclosed.update(spoken)
                if spoken:
                    focus = spoken
                continue
            if _INSTRUCTION_REQUEST.search(text):
                relevant = set()
                focus = set()
                continue
            product_ids = {product.id for product in context.products if mentions_product(product, text)}
            relevant = set()
            previous_topics = {rules[index].topic for index in focus}
            for index, rule in enumerate(rules):
                product_match = bool(product_ids.intersection(rule.product_ids))
                if _matches(rule.question_patterns, text) or product_match:
                    available.add(index)
                direct = _matches(rule.answer_patterns or rule.question_patterns, text)
                contextual = bool(previous_topics.intersection(rule.follow_up_after)) and _matches(rule.follow_up_patterns, text)
                if direct or contextual or product_match:
                    relevant.add(index)
                    available.add(index)
            if not relevant and _FOLLOW_UP.search(text):
                relevant = focus.copy()
            focus = relevant.copy()
        return DisclosureState(
            topics=tuple(rule.topic for index, rule in enumerate(rules) if index in available),
            facts=_facts(context.hidden_needs, rules, available),
            relevant_facts=_facts(context.hidden_needs, rules, relevant),
            disclosed_facts=_facts(context.hidden_needs, rules, disclosed),
        )
