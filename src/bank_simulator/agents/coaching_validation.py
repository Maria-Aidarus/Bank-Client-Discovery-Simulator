"""Conservative checks for observed coaching errors, not a general financial grader."""

import re
from dataclasses import dataclass

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

    def __init__(self, category: str, instruction: str) -> None:
        super().__init__(instruction)
        self.category = category


@dataclass(frozen=True)
class SuitabilityConflict:
    product: BankingProduct
    kind: str


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


def validate_grounding(
    feedback: CoachFeedback, context: CoachingContext, conflicts: tuple[SuitabilityConflict, ...],
) -> None:
    selected = {choice.product_id for choice in context.recommendations}
    student_dialogue = "\n".join(message.content for message in context.transcript
                                 if message.role is MessageRole.STUDENT)
    for product in context.products:
        if product.id in selected or _mentions(product, student_dialogue):
            continue
        if any(_mentions(product, point) and _demands_unselected_product(point)
               for point in feedback.what_was_missed):
            raise CoachingGroundingError(
                "unselected_product_critique",
                "An unselected product was made a required omission without a student product discussion. "
                "Keep its explanation optional in how_to_improve; critique the unresolved client need directly.",
            )
    for conflict in conflicts:
        sharia = conflict.kind.startswith("Sharia")
        def identifies_conflict(point: str) -> bool:
            text = _normalized(point)
            subject = (re.search(r"\b(?:sharia|islamic)\b", text) and re.search(r"\binterest\b", text)) if sharia else (
                re.search(r"\bemergency\b", text) and re.search(r"\b(?:withdraw\w*|delay\w*|same day|immediate|liquidity)\b", text)
            )
            return bool(subject and re.search(
                r"\b(?:conflict\w*|unsuitable|contradict\w*|despite|violat\w*|incompatible|ignored|rejected)\b"
                r"|\b(?:does not|doesn't|fails to) (?:meet|fit|match|respect)\b"
                r"|\bnot (?:suitable|appropriate)\b", text,
            ) and (_mentions(conflict.product, point) or len(conflicts) == 1))

        def gives_correction(point: str) -> bool:
            text = _normalized(point)
            subject = re.search(r"\b(?:sharia|islamic)\b", text) if sharia else re.search(
                r"\b(?:emergency|reserve)\b.{0,65}\b(?:access\w*|liquid\w*|same day|immediate)\b"
                r"|\b(?:access\w*|liquid\w*|same day|immediate)\b.{0,65}\b(?:emergency|reserve)\b", text,
            )
            removes_product = _mentions(conflict.product, text) and re.search(
                r"\b(?:replace|remove|avoid)\b|\bdo not recommend\b", text,
            )
            return bool((subject or removes_product) and re.search(
                r"\b(?:use|keep|separate|replace|remove|avoid|choose|confirm|align|protect|retain|select|consider|assess)\b", text,
            ) and text not in {_normalized(point) for point in feedback.what_was_missed})

        if not any(identifies_conflict(point) for point in feedback.what_was_missed) or not any(
            gives_correction(point) for point in feedback.how_to_improve
        ):
            raise CoachingGroundingError(
                "suitability_sections",
                f"For {conflict.product.name}, identify the {conflict.kind} conflict in what_was_missed, "
                "then give a distinct, practical correction in how_to_improve. Do not merely repeat the same point.",
            )
