"""Authored offline feedback variants, not recovered or newly generated AI output."""

import json
from pathlib import Path

import pytest

from bank_simulator.agents.api_adapter import AIServiceError
from bank_simulator.agents.coach_agent import OllamaCoachAgent
from bank_simulator.models import ProductRecommendation
from bank_simulator.services.coaching_context import build_coaching_context


SCENARIOS = {scenario["id"]: scenario for scenario in json.loads(
    (Path(__file__).resolve().parents[1] / "scripts/conversation_scenarios.json").read_text()
)}
REFUSAL = "I prefer Sharia-compliant financing and I wouldn't take a conventional interest-bearing credit facility."
CONFLICT = "Business Flex Credit contradicts her explicit refusal of conventional financing."
CORRECTION = "Do not recommend the interest-bearing facility; discuss a financing arrangement she would accept."


@pytest.fixture
def maryam_context(content, interviews, recommendations):
    scenario = SCENARIOS["maryam-unsuitable"]
    session = interviews.create_session("maryam")
    replies = ("The business has QAR 25,000 cash and QAR 40,000 due in three weeks.", REFUSAL,
               "No, an interest-bearing revolving line would not work for me.")
    for question, reply in zip(scenario["questions"], replies, strict=True):
        session = interviews.record_student_message(session, question)
        session = interviews.record_client_response(session, reply)
    session = interviews.end_interview(session)
    session = recommendations.submit_summary(session, scenario["summary"])
    session = recommendations.submit_recommendations(session, [
        ProductRecommendation.model_validate(choice) for choice in scenario["recommendations"]
    ])
    return build_coaching_context(session, content)


def _feedback(missed=CONFLICT, correction=CORRECTION):
    return {"what_went_well": ["You established the client's financing restriction."],
            "what_was_missed": [missed], "how_to_improve": [correction]}


@pytest.mark.parametrize("missed", [
    CONFLICT,
    "The proposed interest-based credit disregards her explicit refusal.",
    "Your chosen credit line is incompatible with her stated financing restriction.",
    "The recommendation ignores her Sharia requirement.",
    "You recommended conventional financing despite her saying she would not accept it.",
    "The interest-bearing facility goes against the client's stated preference.",
    "Business Flex Credit is unacceptable given her refusal of conventional credit.",
    "Business Flex Credit is not Sharia-compliant.",
])
def test_equivalent_financing_conflicts_are_accepted_without_repair(maryam_context, scripted_adapter, missed):
    expected = _feedback(missed)
    adapter = scripted_adapter([json.dumps(expected)])
    assert OllamaCoachAgent(adapter).evaluate(maryam_context).model_dump(mode="json") == expected
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("correction", [
    CORRECTION,
    "Withdraw the proposed credit facility and agree an acceptable funding approach.",
    "Drop the conventional credit recommendation and explore acceptable financing instead.",
    "Explore Sharia-compliant arrangements and verify their suitability for the actual obligations.",
    "Rework the financing recommendation to respect her stated refusal.",
    "Replace Business Flex Credit with an approach consistent with the client's requirements.",
])
def test_equivalent_practical_corrections_do_not_require_exact_names(maryam_context, scripted_adapter, correction):
    expected = _feedback(correction=correction)
    adapter = scripted_adapter([json.dumps(expected)])
    assert OllamaCoachAgent(adapter).evaluate(maryam_context).model_dump(mode="json") == expected
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("defect,reason,section", [
    ("advice_only", "missing_suitability_conflict", "what_was_missed"),
    ("absent", "missing_suitability_conflict", "what_was_missed"),
    ("copied", "missing_distinct_correction", "how_to_improve"),
])
def test_missing_misplaced_or_copied_conflicts_still_rejected(maryam_context, scripted_adapter, defect, reason, section):
    invalid = _feedback()
    if defect == "advice_only":
        invalid["what_was_missed"] = ["The cash-flow contingency is unresolved."]
        invalid["how_to_improve"] = [CONFLICT, CORRECTION]
    elif defect == "absent":
        invalid["what_was_missed"] = ["The cash-flow contingency is unresolved."]
        invalid["how_to_improve"] = ["Ask open questions about the business."]
    else:
        repeated = CONFLICT + " " + CORRECTION
        invalid["what_was_missed"] = invalid["how_to_improve"] = [repeated]
    adapter = scripted_adapter([json.dumps(invalid), json.dumps(_feedback())])
    events = []
    assert OllamaCoachAgent(adapter, diagnostics=events.append).evaluate(maryam_context).model_dump(mode="json") == _feedback()
    assert events[0]["reason_code"] == reason
    assert events[0]["failed_section"] == section
    assert events[0]["rule_id"] == "sharia_financing"
    assert len(adapter.calls) == 2
    assert reason not in adapter.calls[1][-1]["content"]  # Repair explains the requirement, not just an opaque code.
    assert section in adapter.calls[1][-1]["content"]


@pytest.mark.parametrize("denial", [
    "Business Flex Credit has no conflict with Sharia requirements despite its interest charges.",
    "Business Flex Credit is not unsuitable for her Sharia requirement.",
    "The conventional facility does not contradict her financing restriction.",
    "The interest-bearing credit line is compatible with her stated requirement.",
    "Business Flex Credit is compatible with her Sharia requirement despite its interest charges.",
    "The conventional facility is not in conflict with her stated Sharia requirement.",
])
def test_negating_the_actual_conflict_cannot_satisfy_the_guard(maryam_context, scripted_adapter, denial):
    adapter = scripted_adapter([json.dumps(_feedback(denial)), json.dumps(_feedback())])
    events = []
    OllamaCoachAgent(adapter, diagnostics=events.append).evaluate(maryam_context)
    assert len(adapter.calls) == 2
    assert events[0]["reason_code"] == "contradicted_requirement"


def test_a_different_product_cannot_stand_in_for_the_selected_conflict(maryam_context, scripted_adapter):
    invalid = _feedback("Goal Saver Account conflicts with her Sharia requirement because it charges interest.")
    adapter = scripted_adapter([json.dumps(invalid), json.dumps(_feedback())])
    events = []
    OllamaCoachAgent(adapter, diagnostics=events.append).evaluate(maryam_context)
    assert len(adapter.calls) == 2
    assert events[0]["reason_code"] == "missing_suitability_conflict"


@pytest.mark.parametrize("optional", [
    ". Optional: Islamic Trade Finance may be considered for a documented eligible future purchase.",
    "; Optional: Islamic Trade Finance may be considered for a documented eligible future purchase.",
    " while Islamic Trade Finance remains an optional alternative for a documented eligible future purchase.",
])
def test_optional_alternative_does_not_inherit_a_neighbouring_critique(maryam_context, scripted_adapter, optional):
    valid = _feedback(
        "You did not assess how Business Flex Credit conflicts with her refusal of interest" + optional
    )
    valid["what_was_missed"].append("A practical contingency for the current cash shortfall remains unresolved.")
    adapter = scripted_adapter([json.dumps(valid)])
    assert OllamaCoachAgent(adapter).evaluate(maryam_context).model_dump(mode="json") == valid
    assert len(adapter.calls) == 1


def test_optional_label_does_not_excuse_mandatory_unselected_product_criticism(maryam_context, scripted_adapter):
    invalid = _feedback()
    invalid["what_was_missed"].append("You failed to select the optional Islamic Trade Finance product.")
    adapter = scripted_adapter([json.dumps(invalid), json.dumps(_feedback())])
    events = []
    OllamaCoachAgent(adapter, diagnostics=events.append).evaluate(maryam_context)
    assert events[0]["reason_code"] == "required_unselected_product"
    assert events[0]["rule_id"] == "optional_product_omission"
    assert len(adapter.calls) == 2


@pytest.mark.parametrize("section,point,reason", [
    ("what_went_well", "You established that Maryam has QAR 99,999 cash.", "unsupported_discovery_figure"),
    ("what_went_well", "You discovered expected receipts of QAR 60,000.", "unsupported_discovery_figure"),
    ("what_was_missed", "You ignored the client's QAR 99,999 cash balance.", "unsupported_financial_figure"),
])
def test_unsupported_financial_claims_are_rejected_without_logging_the_figure(
    maryam_context, scripted_adapter, section, point, reason, caplog,
):
    invalid = _feedback()
    invalid[section] = invalid[section] + [point]
    adapter = scripted_adapter([json.dumps(invalid), json.dumps(_feedback())])
    events = []
    OllamaCoachAgent(adapter, diagnostics=events.append).evaluate(maryam_context)
    assert events[0]["reason_code"] == reason
    assert events[0]["rule_id"] == "financial_evidence"
    assert point not in caplog.text + json.dumps(events)
    assert len(adapter.calls) == 2


def test_grounded_calculations_and_hypothetical_questions_are_allowed(maryam_context, scripted_adapter):
    valid = _feedback()
    valid["what_went_well"].append("You calculated a QAR 15,000 gap after comparing cash and payments due.")
    valid["how_to_improve"].append("Ask whether a QAR 1,000 contingency could be available; do not assume it exists.")
    adapter = scripted_adapter([json.dumps(valid)])
    assert OllamaCoachAgent(adapter).evaluate(maryam_context).model_dump(mode="json") == valid
    assert len(adapter.calls) == 1


def test_each_attempt_reports_its_own_reason_section_and_timing_without_bodies(
    maryam_context, scripted_adapter, monkeypatch, caplog,
):
    clock = iter((10.0, 11.25, 20.0, 22.5))
    monkeypatch.setattr("bank_simulator.agents.coach_agent.monotonic", lambda: next(clock))
    first = _feedback("A cash contingency remains unresolved.")
    first["what_went_well"].append("private-response-marker personal-name-marker")
    second = _feedback(correction="Use open questions. private-response-marker")
    adapter = scripted_adapter([json.dumps(first), json.dumps(second)])
    events = []
    with pytest.raises(AIServiceError) as error:
        OllamaCoachAgent(adapter, diagnostics=events.append).evaluate(maryam_context)
    assert error.value.category == "coach_grounding"
    assert len(adapter.calls) == 2
    assert [(e["attempt_index"], e["reason_code"], e["failed_section"], e["rule_id"], e["elapsed_seconds"]) for e in events] == [
        (0, "missing_suitability_conflict", "what_was_missed", "sharia_financing", 1.25),
        (1, "missing_distinct_correction", "how_to_improve", "sharia_financing", 2.5),
    ]
    assert len(caplog.records) == 2  # Default server logging works without wiring a frontend sink.
    for marker in ("private-response-marker", "personal-name-marker", "Maryam", "QAR", "Business Flex Credit"):
        assert marker not in caplog.text + json.dumps(events)
    assert [options["max_tokens"] for options in adapter.options] == [8192, 8192]


def test_default_server_diagnostics_work_without_an_optional_sink(maryam_context, scripted_adapter, caplog):
    invalid = _feedback(correction="Use open questions.")
    adapter = scripted_adapter([json.dumps(invalid), json.dumps(_feedback())])
    OllamaCoachAgent(adapter).evaluate(maryam_context)
    assert "attempt_index=0" in caplog.text
    assert "reason_code=missing_distinct_correction" in caplog.text
    assert "failed_section=how_to_improve" in caplog.text
    assert "rule_id=sharia_financing" in caplog.text
    assert "elapsed_seconds=" in caplog.text


def test_generation_failure_is_separate_from_feedback_validation(maryam_context, scripted_adapter, caplog):
    adapter = scripted_adapter([AIServiceError("private-exception-marker", category="private-category-marker")])
    events = []
    with pytest.raises(AIServiceError):
        OllamaCoachAgent(adapter, diagnostics=events.append).evaluate(maryam_context)
    assert len(adapter.calls) == len(events) == 1
    assert events[0]["stage"] == "coach_generation"
    assert events[0]["reason_code"] == "api_error"
    assert events[0]["rule_id"] == "usable_final_answer"
    assert "stage=coach_generation" in caplog.text
    assert "private-exception-marker" not in caplog.text + json.dumps(events)
    assert "private-category-marker" not in caplog.text + json.dumps(events)


def test_reversing_the_clients_stated_refusal_is_rejected(maryam_context, scripted_adapter):
    invalid = _feedback()
    invalid["what_went_well"] = ["You confirmed that she accepts conventional interest-bearing credit."]
    adapter = scripted_adapter([json.dumps(invalid), json.dumps(_feedback())])
    events = []
    OllamaCoachAgent(adapter, diagnostics=events.append).evaluate(maryam_context)
    assert events[0]["reason_code"] == "contradicted_requirement"
    assert events[0]["failed_section"] == "what_went_well"
    assert len(adapter.calls) == 2


def test_acknowledging_cash_benefit_does_not_deny_the_financing_conflict(maryam_context, scripted_adapter):
    valid = _feedback(
        "Business Flex Credit is suitable for short cash gaps but contradicts her refusal of conventional financing."
    )
    valid["what_went_well"] = ["You established that she accepts Islamic arrangements but not interest-bearing loans."]
    adapter = scripted_adapter([json.dumps(valid)])
    assert OllamaCoachAgent(adapter).evaluate(maryam_context).model_dump(mode="json") == valid
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("missed,correction", [
    ("This account cannot meet the same-day access needed for urgent repairs.",
     "Move the emergency reserve somewhere immediately accessible; assess planned goal savings separately."),
    ("The withdrawal delay makes the chosen account a poor fit for an emergency reserve.",
     "Emergency funds must stay accessible the same day."),
    ("Locking the emergency reserve ignores the need to access it immediately.",
     "Transfer emergency funds to an instant-access reserve and discuss dated savings separately."),
])
def test_mohamed_equivalent_liquidity_feedback_is_accepted(
    content, interviews, recommendations, scripted_adapter, missed, correction,
):
    scenario = SCENARIOS["mohamed-unsuitable"]
    session = interviews.create_session("mohamed")
    for question, reply in zip(scenario["questions"], (
        "I have QAR 1,200 set aside.", "I need it available the same day for an unexpected repair.",
        "No, I cannot wait several business days for emergency money.",
    ), strict=True):
        session = interviews.record_student_message(session, question)
        session = interviews.record_client_response(session, reply)
    session = recommendations.submit_summary(interviews.end_interview(session), scenario["summary"])
    session = recommendations.submit_recommendations(session, [
        ProductRecommendation.model_validate(choice) for choice in scenario["recommendations"]
    ])
    expected = _feedback(missed, correction)
    adapter = scripted_adapter([json.dumps(expected)])
    assert OllamaCoachAgent(adapter).evaluate(build_coaching_context(session, content)).model_dump(mode="json") == expected
    assert len(adapter.calls) == 1
