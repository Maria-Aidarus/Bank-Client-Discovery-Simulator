"""Conservative checks for observed coaching errors, not a general financial grader."""

import re
from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations

from ..models import BankingProduct, CoachFeedback, CoachingContext, MessageRole


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[-‐‑‒–—]", " ", text.lower().replace("’", "'")))


def _mentions(product: BankingProduct, text: str) -> bool:
    """Recognize a catalogue name or its distinctive two-word category."""
    words = _normalized(product.name).split()
    names = {_normalized(product.name), _normalized(product.id)}
    if len(words) >= 3:
        names.add(" ".join(words[:-1] if words[-1] == "account" else words[1:]))
    if "finance" in words and re.search(r"\bpurchase\b", _normalized(product.description)):
        names.add("purchase finance")
    return any(re.search(r"\b" + re.escape(name) + r"\b", _normalized(text)) for name in names)


class CoachingGroundingError(ValueError):
    """Feedback needs the existing single model repair, never a fabricated replacement."""

    def __init__(
        self, category: str, instruction: str, *, reason_code: str,
        section: str, rule_id: str,
    ) -> None:
        super().__init__(instruction)
        self.category = category
        self.reason_code = reason_code
        self.section = section
        self.rule_id = rule_id


@dataclass(frozen=True)
class SuitabilityConflict:
    product: BankingProduct
    kind: str

    @property
    def rule_id(self) -> str:
        return "sharia_financing" if self.kind.startswith("Sharia") else "emergency_liquidity"


def confirmed_conflicts(context: CoachingContext) -> tuple[SuitabilityConflict, ...]:
    """Detect only explicit, supported conflicts in the two known requirement families.

    Read actual Client statements and editable catalogue terms, never client IDs.
    Ambiguous preferences or an unspecified use of an account remain model judgments.
    """
    statements = [_normalized(message.content) for message in context.transcript
                  if message.role is MessageRole.CLIENT]
    sharia_required = any(re.search(
        r"\b(?:require|need|must|only accept)\b.{0,60}\b(?:sharia|islamic)\b"
        r"|\b(?:decline|reject|won't accept|wouldn't accept|wouldn't take|will not accept)\b"
        r".{0,60}\b(?:interest|conventional)\b", statement,
    ) and not re.search(r"\b(?:do not|don't) (?:need|require)\b", statement) for statement in statements)
    immediate_access = any(re.search(
        r"\b(?:need|require|must|have to)\b.{0,70}\b(?:same day|immediate|instantly|right away|straight away)\b"
        r"|\b(?:same day|immediate) access\b.{0,25}\b(?:essential|required|necessary)\b", statement,
    ) and not re.search(r"\b(?:do not|don't) (?:need|require)\b", statement) for statement in statements)
    products = {product.id: product for product in context.products}
    result = []
    for choice in context.recommendations:
        product = products[choice.product_id]
        terms = _normalized(" ".join((product.description, *product.key_features, *product.limitations)))
        if sharia_required and re.search(r"\binterest (?:bearing|applies)\b", terms):
            result.append(SuitabilityConflict(product, "Sharia requirement versus interest-bearing financing"))
        # A goal account is not unsuitable merely because the client also needs an
        # emergency reserve. Require evidence that THIS recommendation assigns it
        # emergency money, rather than funds explicitly held separately.
        emergency_assignment = re.search(
            r"\b(?:put|move|place|hold|keep|park|deposit|store|lock)\b.{0,45}\bemergency\b"
            r"|\b(?:for|use|all|entire)\b.{0,20}\bemergency (?:money|funds|savings|reserve)\b",
            _normalized(choice.justification),
        )
        emergency_separate = re.search(
            r"\bemergency\b.{0,40}\b(?:separate from|elsewhere|outside|out of)\b"
            r"|\bseparate emergency (?:reserve|funds|savings)\b", _normalized(choice.justification),
        )
        delayed_withdrawals = re.search(r"\bwithdrawals?\b.{0,45}\b(?:several|business) days\b", terms)
        if immediate_access and emergency_assignment and not emergency_separate and delayed_withdrawals:
            result.append(SuitabilityConflict(product, "Emergency liquidity versus delayed withdrawals"))
    return tuple(result)


def _demands_unselected_product(point: str) -> bool:
    text = _normalized(point)
    return bool(re.search(
        r"\b(?:failed to|did not|didn't|should have|must|needed to)\b.{0,45}"
        r"\b(?:consider|select|recommend|offer|choose|explain|discuss|evaluate|test|clarify|assess)\b"
        r"|\b(?:omitted|missed|overlooked|neglected|no explanation)\b"
        r"|\b(?:coverage|boundary|boundaries|eligibility|structure|limitations|terms)\b"
        r".{0,80}\b(?:not|wasn't|isn't|unexplored|untested|unclear)\b", text,
    ))


def _clauses(point: str) -> list[str]:
    """Keep a neighbouring optional suggestion out of an unrelated critique."""
    return re.split(
        r"(?<=[.!?;])\s+|,\s+(?=optional\b)"
        r"|\s+(?:while|whereas|but)\s+(?=[^.;!?]*\boptional\b)", _normalized(point),
    )


def _refers_to_choice(
    text: str, conflict: SuitabilityConflict, context: CoachingContext,
    conflicts: tuple[SuitabilityConflict, ...],
) -> bool:
    if _mentions(conflict.product, text):
        return True
    if any(_mentions(product, text) for product in context.products):
        return False  # A different named product cannot stand in for this choice.
    # A description such as "the interest-bearing facility" can resolve a unique
    # selected conflict. Multiple conflicting choices require disambiguation.
    return sum(item.rule_id == conflict.rule_id for item in conflicts) == 1


_CONFLICT = re.compile(
    r"\b(?:conflict\w*|unsuitable|contradict\w*|despite|violat\w*|incompatible|ignor\w*|"
    r"reject\w*|declin\w*|disregard\w*|unacceptable|against|clash\w*|although)\b"
    r"|\b(?:at odds|contrary to|even though|does not|doesn't|fails to|cannot|can't)\b"
    r".{0,25}\b(?:meet|fit|match|respect|comply|accept|suit)\b"
    r"|\bnot (?:suitable|appropriate)\b"
    r"|\b(?:poor fit|not for)\b"
    r"|\b(?:not|isn't) (?:sharia |islamic )?compliant\b"
)
_NEGATED_CONFLICT = re.compile(
    r"\b(?:no|not (?:a |an |in )?)\s*(?:conflict|problem|contradiction)\b"
    r"|\bnot (?:unsuitable|incompatible)\b"
    r"|\b(?:does not|doesn't) (?:conflict|contradict|violate)\b"
)
_FINANCING = re.compile(r"\b(?:sharia|islamic|interest|conventional|credit|financing|facility)\b")
_REQUIREMENT = re.compile(
    r"\b(?:sharia|islamic|refus\w*|reject\w*|declin\w*|require\w*|restrict\w*|prefer\w*)\b"
    r"|\b(?:would not|will not|wouldn't|won't|cannot|can't) (?:accept|take|use)\b"
)
_LIQUIDITY = re.compile(r"\b(?:withdraw\w*|delay\w*|same day|immediat\w*|instant\w*|liquid\w*|access\w*|wait)\b")
_CORRECTION = re.compile(
    r"\b(?:use|keep|separate|replace|remove|avoid|choose|confirm|align|protect|retain|select|consider|assess|"
    r"withdraw|drop|stop|discuss|explore|agree|arrange|rework|revise|switch|find|propose|reject|move|transfer|put|leave|maintain|stay)\b"
    r"|\bdo not recommend\b|\bdon't recommend\b"
)


def _identifies_conflict(text: str, conflict: SuitabilityConflict) -> bool:
    if _NEGATED_CONFLICT.search(text) or not _CONFLICT.search(text):
        return False
    if conflict.rule_id == "sharia_financing":
        return bool(_FINANCING.search(text) and _REQUIREMENT.search(text))
    return bool(_LIQUIDITY.search(text) and re.search(
        r"\b(?:emergency|reserve|unexpected|urgent|require\w*|need\w*)\b", text,
    ))


def _corrects_conflict(text: str, conflict: SuitabilityConflict) -> bool:
    if not _CORRECTION.search(text):
        return False
    if conflict.rule_id == "sharia_financing":
        return bool(
            re.search(r"\b(?:sharia|islamic|acceptable|accept\w*|compliant|non interest)\b", text)
            or (_FINANCING.search(text) and re.search(
                r"\b(?:do not|don't|stop|drop|remove|avoid|withdraw|reject|replace|switch|revise|rework)\b", text,
            ))
        )
    return bool(
        re.search(r"\b(?:emergency|reserve|unexpected|urgent)\b", text) and _LIQUIDITY.search(text)
        or re.search(r"\b(?:delayed|restrictive|locked)\b", text) and re.search(
            r"\b(?:replace|remove|avoid|stop|switch|drop)\b", text,
        )
    )


def _denies_known_conflict(text: str, conflict: SuitabilityConflict) -> bool:
    """Reject clear inversions, while allowing criticism of a mistaken claim."""
    if re.search(r"\b(?:incorrectly|wrongly|falsely|mistaken|unsupported|not true)\b", text):
        return False
    scope = _FINANCING.search(text) if conflict.rule_id == "sharia_financing" else _LIQUIDITY.search(text)
    requirement = r"(?:sharia|islamic|refusal|stated requirement|financing restriction)" if conflict.rule_id == "sharia_financing" else (
        r"(?:emergency|same day|immediate access|access requirement)"
    )
    reverses_refusal = conflict.rule_id == "sharia_financing" and re.search(
        r"\b(?:client|customer|she|he)\b.{0,20}\b(?:accepts?|accepted|agreed to|comfortable with)\b"
        r"\s+(?:(?:a|an|the|any|standard)\s+)?(?:interest|conventional)\b", text,
    )
    # A concession such as "despite interest" must not turn an explicit claim of
    # compatibility into a valid conflict warning. Conversely, acknowledging a
    # cash-flow benefit is not an endorsement against the client's requirement.
    explicit_compatibility = re.search(
        r"\b(?:is|remains|would be) (?:fully )?(?:compatible|compliant)\b.{0,55}\b" + requirement, text,
    ) or re.search(
        r"\b(?:is|remains|would be) (?:fully )?(?:suitable|appropriate) for "
        r"(?:(?:her|his|the|an?) )?" + requirement, text,
    )
    if scope and (reverses_refusal or _NEGATED_CONFLICT.search(text) or explicit_compatibility):
        return True
    if _identifies_conflict(text, conflict):
        return False
    return bool(scope and (
        re.search(r"\b(?:meets|respects|satisfies)\b.{0,35}\b" + requirement, text)
    ))


def _amounts(text: str) -> set[Decimal]:
    return {Decimal(value.replace(",", "")) for value in re.findall(
        r"\bQAR\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\b", text, re.IGNORECASE,
    )}


def _validate_amount_claims(feedback: CoachFeedback, context: CoachingContext) -> None:
    """Reject clear invented currency claims, allowing questions and simple arithmetic.

    This is an evidence guard, not a general fact checker. Benchmark facts may be
    used to explain missed needs, but are not proof of discovery in strengths.
    """
    transcript = _amounts(context.client_profile.model_dump_json() + "\n" + "\n".join(
        message.content for message in context.transcript
    ))
    evidence = _amounts(context.model_dump_json())
    for section in ("what_went_well", "what_was_missed", "how_to_improve"):
        source = transcript if section == "what_went_well" else evidence
        for point in getattr(feedback, section):
            for clause in _clauses(point):
                if section == "how_to_improve" and re.match(
                    r"(?:ask|consider|for example|if|suppose|could|would|discuss whether)\b", clause,
                ):
                    continue
                supported = set(source)
                if re.search(r"\b(?:gap|shortfall|difference|after|remaining|surplus|minus|total|plus|sum)\b", clause):
                    for left, right in combinations(source, 2):
                        supported.update((left + right, abs(left - right)))
                if _amounts(clause) - supported:
                    raise CoachingGroundingError(
                        "evidence_grounding", "Use only supported financial figures. Do not credit a benchmark-only "
                        "figure as discovered; keep a hypothetical amount clearly labelled as a question or example.",
                        reason_code="unsupported_discovery_figure" if section == "what_went_well" else "unsupported_financial_figure",
                        section=section, rule_id="financial_evidence",
                    )


def validate_grounding(
    feedback: CoachFeedback, context: CoachingContext, conflicts: tuple[SuitabilityConflict, ...],
) -> None:
    _validate_amount_claims(feedback, context)
    selected = {choice.product_id for choice in context.recommendations}
    student_dialogue = "\n".join(message.content for message in context.transcript
                                 if message.role is MessageRole.STUDENT)
    for product in context.products:
        if product.id in selected or _mentions(product, student_dialogue):
            continue
        if any(_mentions(product, clause) and _demands_unselected_product(clause)
               for point in feedback.what_was_missed for clause in _clauses(point)):
            raise CoachingGroundingError(
                "unselected_product_critique",
                "An unselected product was made a required omission without a student product discussion. "
                "Keep its explanation optional in how_to_improve; critique the unresolved client need directly.",
                reason_code="required_unselected_product", section="what_was_missed",
                rule_id="optional_product_omission",
            )
    for conflict in conflicts:
        for section in ("what_went_well", "what_was_missed", "how_to_improve"):
            for point in getattr(feedback, section):
                for clause in _clauses(point):
                    if _refers_to_choice(clause, conflict, context, conflicts) and _denies_known_conflict(clause, conflict):
                        raise CoachingGroundingError(
                            "suitability_sections", "Do not endorse the selected product as meeting a requirement it contradicts.",
                            reason_code="contradicted_requirement", section=section, rule_id=conflict.rule_id,
                        )
        if not any(
            _refers_to_choice(clause, conflict, context, conflicts) and _identifies_conflict(clause, conflict)
            for point in feedback.what_was_missed for clause in _clauses(point)
        ):
            raise CoachingGroundingError(
                "suitability_sections",
                f"In what_was_missed, explicitly connect the submitted {conflict.product.name} "
                f"to the client's stated refusal/access requirement ({conflict.kind}). "
                "Equivalent grounded wording is acceptable; the warning must not appear only in how_to_improve.",
                reason_code="missing_suitability_conflict", section="what_was_missed", rule_id=conflict.rule_id,
            )
        missed = {_normalized(point) for point in feedback.what_was_missed}
        if not any(
            _normalized(point) not in missed and any(_corrects_conflict(clause, conflict) for clause in _clauses(point))
            for point in feedback.how_to_improve
        ):
            raise CoachingGroundingError(
                "suitability_sections",
                "In how_to_improve, give a distinct practical correction: "
                + ("withdraw the interest-bearing choice and discuss financing the client would accept. "
                   if conflict.rule_id == "sharia_financing" else
                   "keep emergency money immediately accessible and assess dated-goal savings separately. ")
                + "Do not merely repeat the criticism from what_was_missed.",
                reason_code="missing_distinct_correction", section="how_to_improve", rule_id=conflict.rule_id,
            )
