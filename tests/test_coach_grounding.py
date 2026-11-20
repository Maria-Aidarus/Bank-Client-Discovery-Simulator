"""Regressions for the observed deployed feedback; all completions are test doubles."""

import json

import pytest

from bank_simulator.agents.api_adapter import AIServiceError
from bank_simulator.agents.coach_agent import OllamaCoachAgent
from bank_simulator.models import ProductRecommendation
from bank_simulator.services.coaching_context import build_coaching_context


def _context(content, interviews, recommendations, client, reply, choices, summary="Original student summary."):
    session = interviews.create_session(client)
    session = interviews.record_student_message(session, "What requirements should guide this recommendation?")
    session = interviews.record_client_response(session, reply)
    session = interviews.end_interview(session)
    session = recommendations.submit_summary(session, summary)
    session = recommendations.submit_recommendations(session, [
        ProductRecommendation(product_id=product, justification=reason) for product, reason in choices
    ])
    return build_coaching_context(session, content)


@pytest.fixture(params=["sharia", "liquidity"])
def conflict(request, content, interviews, recommendations):
    if request.param == "sharia":
        context = _context(content, interviews, recommendations, "maryam",
                           "I would decline conventional interest-bearing credit. I require Sharia-compliant financing.",
                           [("business-flex-credit", "Cover the bills despite the stated preference.")])
        missed = "Business Flex Credit is unsuitable: its interest conflicts with the explicit Sharia requirement."
        advice = "Replace that recommendation with a Sharia-compliant approach, subject to suitability and approval."
    else:
        context = _context(content, interviews, recommendations, "mohamed",
                           "I need same-day access to my emergency money if an unexpected bill arrives.",
                           [("goal-saver-account", "Put all emergency money here despite the withdrawal delay.")])
        missed = "Goal Saver Account is unsuitable for emergency money because delayed withdrawals conflict with same-day access."
        advice = "Keep emergency funds in an instant-access reserve and assess dated goal savings separately."
    feedback = {"what_went_well": ["You asked about requirements."],
                "what_was_missed": [missed], "how_to_improve": [advice]}
    return context, feedback


def test_confirmed_conflict_in_correct_sections_is_accepted_without_repair(conflict, scripted_adapter):
    context, feedback = conflict
    adapter = scripted_adapter([json.dumps(feedback)])
    assert OllamaCoachAgent(adapter).evaluate(context).model_dump(mode="json") == feedback
    assert len(adapter.calls) == 1
    assert "Identify the conflict in what_was_missed" in adapter.calls[0][0]["content"]


@pytest.mark.parametrize("defect", ["advice_only", "missing_correction", "identical_explanation"])
def test_each_client_conflict_requires_identification_and_distinct_correction(conflict, scripted_adapter, defect):
    context, corrected = conflict
    invalid = dict(corrected)
    if defect == "advice_only":
        invalid["what_was_missed"] = ["Other follow-up questions remain."]
        invalid["how_to_improve"] = corrected["what_was_missed"] + corrected["how_to_improve"]
    elif defect == "missing_correction":
        invalid["how_to_improve"] = ["Listen carefully and ask open questions."]
    else:
        repeated = corrected["what_was_missed"][0] + " " + corrected["how_to_improve"][0]
        invalid["what_was_missed"] = invalid["how_to_improve"] = [repeated]
    events = []
    adapter = scripted_adapter([json.dumps(invalid), json.dumps(corrected)])
    result = OllamaCoachAgent(adapter, diagnostics=events.append).evaluate(context)
    assert result.model_dump(mode="json") == corrected
    assert len(adapter.calls) == 2
    assert events[0]["validation_failure_category"] == "suitability_sections"
    assert "what_was_missed" in adapter.calls[1][-1]["content"]
    assert "distinct" in adapter.calls[1][-1]["content"]


def test_section_repair_exhaustion_does_not_fabricate_or_relocate_feedback(conflict, scripted_adapter):
    context, valid = conflict
    invalid = {**valid, "what_was_missed": []}
    adapter = scripted_adapter([json.dumps(invalid)] * 2)
    with pytest.raises(AIServiceError) as error:
        OllamaCoachAgent(adapter).evaluate(context)
    assert error.value.category == "coach_grounding"
    assert len(adapter.calls) == 2


@pytest.mark.parametrize("category", ["Sharia trade-finance", "purchase finance", "Islamic Trade Finance"])
def test_category_omissions_get_repaired_while_real_cash_gap_critique_survives(
    content, interviews, recommendations, scripted_adapter, category,
):
    context = _context(content, interviews, recommendations, "maryam",
                       "The business has QAR 25,000 available and QAR 40,000 due.",
                       [("business-cash-management", "Visibility only. It supplies no financing; a contingency is required.")],
                       "A QAR 15,000 timing gap. Purchase finance needs qualifying documentation.")
    invalid = {"what_went_well": ["You acknowledged the no-funding limitation."],
               "what_was_missed": [f"The {category} coverage boundary was not tested: its scope does not cover payroll."],
               "how_to_improve": ["Optional: consider Islamic Trade Finance for documented eligible future purchases."]}
    corrected = {**invalid, "what_was_missed": ["A contingency for the remaining cash gap has not been agreed."]}
    adapter = scripted_adapter([json.dumps(invalid), json.dumps(corrected)])
    result = OllamaCoachAgent(adapter).evaluate(context)
    assert result.model_dump(mode="json") == corrected
    assert len(adapter.calls) == 2
    assert "Move alternatives" in adapter.calls[1][-1]["content"]


def test_unselected_category_can_explain_an_unresolved_need_without_becoming_mandatory(
    content, interviews, recommendations, scripted_adapter,
):
    context = _context(content, interviews, recommendations, "maryam", "Supplier payments are due soon.",
                       [("business-cash-management", "Visibility only; provides no funding.")])
    feedback = {"what_went_well": ["You acknowledged that visibility is not financing."],
                "what_was_missed": ["A funding contingency remains unresolved; trade finance cannot cover existing payroll."],
                "how_to_improve": ["Ask what available contingency could cover the payments if receipts slip."]}
    adapter = scripted_adapter([json.dumps(feedback)])
    assert OllamaCoachAgent(adapter).evaluate(context).model_dump(mode="json") == feedback
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("justification", [
    "For the certification goal, with adjustable contributions and a separate emergency reserve.",
    "Keep emergency savings separate from this account; this is for certification only.",
])
def test_access_requirement_does_not_make_separate_goal_savings_unsuitable(
    content, interviews, recommendations, scripted_adapter, justification,
):
    context = _context(content, interviews, recommendations, "mohamed", "I need same-day access to emergency money.",
                       [("goal-saver-account", justification),
                        ("everyday-access-account", "For an accessible emergency reserve.")])
    feedback = {"what_went_well": ["You separated dated savings from the emergency reserve."],
                "what_was_missed": ["The affordable contribution remains uncertain."],
                "how_to_improve": ["Check irregular expenses before agreeing a contribution."]}
    adapter = scripted_adapter([json.dumps(feedback)])
    assert OllamaCoachAgent(adapter).evaluate(context).model_dump(mode="json") == feedback
    assert len(adapter.calls) == 1


def test_private_benchmark_and_student_question_are_not_proof_of_an_explicit_requirement(
    content, interviews, recommendations, scripted_adapter,
):
    context = _context(content, interviews, recommendations, "maryam", "I would like to review my banking.",
                       [("business-flex-credit", "It might help with payments.")])
    feedback = {"what_went_well": [], "what_was_missed": ["Financing preferences were not explored."],
                "how_to_improve": ["Ask what financing arrangements the client would accept."]}
    adapter = scripted_adapter([json.dumps(feedback)])
    assert OllamaCoachAgent(adapter).evaluate(context).model_dump(mode="json") == feedback
    assert len(adapter.calls) == 1
