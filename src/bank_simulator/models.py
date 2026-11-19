"""Validated content, interview state, and agent inputs and outputs."""

import re
from datetime import UTC, datetime
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TextItems = Annotated[tuple[Text, ...], Field(min_length=1)]


def _require_nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("must contain non-whitespace text")
    return value


OriginalText = Annotated[str, AfterValidator(_require_nonblank)]


class _ValidatedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClientProfile(_ValidatedModel):
    """Information students can see before choosing a client."""

    id: Identifier
    name: Text
    age: Annotated[int, Field(strict=True, gt=0, le=125)]
    occupation: Text
    background: Text
    public_financial_situation: Text
    interview_opening_context: Text


class DisclosureFactReference(_ValidatedModel):
    """A zero-based reference into one of the private fact lists."""

    section: Literal[
        "private_financial_facts", "financial_concerns", "important_constraints",
        "banking_preferences", "hidden_needs",
    ]
    index: Annotated[int, Field(strict=True, ge=0)]


class DisclosureTopic(_ValidatedModel):
    """A topic and the circumstances under which a client can discuss it."""

    topic: Text
    reveal_when: Text
    question_patterns: tuple[Text, ...] = ()
    fact_references: tuple[DisclosureFactReference, ...] = ()

    @model_validator(mode="after")
    def _validate_rules(self) -> Self:
        if bool(self.question_patterns) != bool(self.fact_references):
            raise ValueError("disclosure patterns and fact references must be supplied together")
        for pattern in self.question_patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
            except re.error:
                raise ValueError("disclosure question pattern must be a valid regular expression") from None
            if compiled.search(""):
                raise ValueError("disclosure question patterns must not match empty text")
        return self


class DiscoveryExpectation(_ValidatedModel):
    """A discovery objective with optional catalogue references for the coach."""

    description: Text
    related_product_ids: tuple[Identifier, ...] = ()


class HiddenNeeds(_ValidatedModel):
    """Private client facts and guidance for the agents."""

    client_id: Identifier
    private_financial_facts: TextItems
    financial_concerns: TextItems
    important_constraints: TextItems
    banking_preferences: TextItems
    hidden_needs: TextItems
    disclosure_topics: Annotated[tuple[DisclosureTopic, ...], Field(min_length=1)]
    discovery_expectations: Annotated[tuple[DiscoveryExpectation, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _validate_disclosure_references(self) -> Self:
        for topic in self.disclosure_topics:
            for reference in topic.fact_references:
                if reference.index >= len(getattr(self, reference.section)):
                    raise ValueError(f"disclosure topic '{topic.topic}' references a nonexistent fact")
        return self


class BankingProduct(_ValidatedModel):
    """A fictional product and the conditions that affect its suitability."""

    id: Identifier
    name: Text
    description: Text
    key_features: TextItems
    benefits: TextItems
    limitations: TextItems
    eligibility_requirements: TextItems
    suitable_use_cases: TextItems
    unsuitable_use_cases: TextItems


class MessageRole(StrEnum):
    STUDENT = "student"
    CLIENT = "client"


class InterviewStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"


class InterviewMessage(_ValidatedModel):
    role: MessageRole
    content: OriginalText
    timestamp: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))


def _validate_transcript(messages: tuple[InterviewMessage, ...]) -> tuple[InterviewMessage, ...]:
    if any(first.timestamp > second.timestamp for first, second in pairwise(messages)):
        raise ValueError("transcript timestamps must be in chronological order")
    return messages


Transcript = Annotated[tuple[InterviewMessage, ...], AfterValidator(_validate_transcript)]


class ProductRecommendation(_ValidatedModel):
    product_id: Identifier
    justification: OriginalText


def _validate_recommendations(
    recommendations: tuple[ProductRecommendation, ...],
) -> tuple[ProductRecommendation, ...]:
    if len({item.product_id for item in recommendations}) != len(recommendations):
        raise ValueError("each product may be recommended only once")
    return recommendations


Recommendations = Annotated[
    tuple[ProductRecommendation, ...], AfterValidator(_validate_recommendations)
]


class InterviewSession(_ValidatedModel):
    """One student's interview and post-interview work."""

    session_id: UUID = Field(default_factory=uuid4)
    client_id: Identifier | None = None
    transcript: Transcript = ()
    status: InterviewStatus = InterviewStatus.DRAFT
    student_summary: OriginalText | None = None
    selected_recommendations: Recommendations = ()

    @model_validator(mode="after")
    def _validate_state(self) -> Self:
        if self.status is InterviewStatus.DRAFT:
            if self.client_id is not None or self.transcript:
                raise ValueError("a draft interview cannot have a client or messages")
        elif self.client_id is None:
            raise ValueError("an active or completed interview requires a client")

        if self.status is not InterviewStatus.COMPLETED:
            if self.student_summary is not None or self.selected_recommendations:
                raise ValueError("complete the interview before submitting student work")
        if self.selected_recommendations and self.student_summary is None:
            raise ValueError("recommendations require a student summary")
        return self

    def validated_update(self, **changes: object) -> Self:
        """Return a new snapshot after validating fields and state together."""
        return type(self).model_validate({**dict(self), **changes})


class InterviewContext(_ValidatedModel):
    """Server-side input to the client agent before disclosure filtering."""

    client_profile: ClientProfile
    hidden_needs: HiddenNeeds
    transcript: Transcript

    @model_validator(mode="after")
    def _validate_client(self) -> Self:
        if self.client_profile.id != self.hidden_needs.client_id:
            raise ValueError("public profile and hidden needs must belong to the same client")
        return self


class CoachingContext(InterviewContext):
    """Server-side input to the coach agent after student submission."""

    products: Annotated[tuple[BankingProduct, ...], Field(min_length=1)]
    student_summary: OriginalText
    recommendations: Annotated[Recommendations, Field(min_length=1)]

    @model_validator(mode="after")
    def _validate_catalogue(self) -> Self:
        product_ids = {product.id for product in self.products}
        if len(product_ids) != len(self.products):
            raise ValueError("the coaching catalogue must have unique product IDs")
        for recommendation in self.recommendations:
            if recommendation.product_id not in product_ids:
                raise ValueError(f"unknown product ID '{recommendation.product_id}'")
        return self


class CoachFeedback(_ValidatedModel):
    """Structured feedback, with an empty list allowed for any section."""

    what_went_well: tuple[Text, ...]
    what_was_missed: tuple[Text, ...]
    how_to_improve: tuple[Text, ...]
