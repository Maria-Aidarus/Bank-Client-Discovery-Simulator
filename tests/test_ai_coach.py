import json

import pytest

from bank_simulator.agents.api_adapter import AIServiceError
from bank_simulator.agents.coach_agent import OllamaCoachAgent
from bank_simulator.models import CoachFeedback, ProductRecommendation
from bank_simulator.services.coaching_context import build_coaching_context


FEEDBACK = {
    "what_went_well": ["You asked what the client was saving for."],
    "what_was_missed": ["Emergency access was not explored in the interview."],
    "how_to_improve": ["Ask how quickly the client would need emergency funds."],
}


@pytest.fixture
def coaching_context(content, recommendations, completed_interview):
    session = recommendations.submit_summary(completed_interview, "  A dated certification goal.\n")
    session = recommendations.submit_recommendations(session, [ProductRecommendation(
        product_id="business-flex-credit", justification="I think credit sounds useful.",
    )])
    return build_coaching_context(session, content)


def test_coach_receives_complete_evidence_and_returns_feedback(coaching_context, scripted_adapter):
    adapter = scripted_adapter([json.dumps(FEEDBACK)])
    result = OllamaCoachAgent(adapter).evaluate(coaching_context)
    assert result == CoachFeedback.model_validate(FEEDBACK)
    messages, = adapter.calls
    assert json.loads(messages[1]["content"]) == coaching_context.model_dump(mode="json")
    assert len(json.loads(messages[1]["content"])["transcript"]) == 2
    assert len(json.loads(messages[1]["content"])["products"]) == 5
    assert "limitations" in messages[1]["content"]
    assert "business-flex-credit" in messages[1]["content"]
    assert "I think credit sounds useful." in messages[1]["content"]
    assert "Maryam" not in messages[1]["content"]
    assert "A summary claim without" in messages[0]["content"]
    assert "gender" in messages[0]["content"]
    assert "do not claim the student omitted" in messages[0]["content"]


def test_fenced_json_is_safely_parsed_without_repair(coaching_context, scripted_adapter):
    adapter = scripted_adapter(["```json\n" + json.dumps(FEEDBACK) + "\n```"])
    assert OllamaCoachAgent(adapter).evaluate(coaching_context).what_went_well
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("malformed", [
    "Here is your feedback", "{broken-json", json.dumps({"what_went_well": ["A question"]}),
    json.dumps({**FEEDBACK, "score": 100}), json.dumps({**FEEDBACK, "how_to_improve": "Ask more"}),
])
def test_malformed_feedback_gets_exactly_one_repair(coaching_context, scripted_adapter, malformed):
    adapter = scripted_adapter([malformed, json.dumps(FEEDBACK)])
    assert OllamaCoachAgent(adapter).evaluate(coaching_context) == CoachFeedback.model_validate(FEEDBACK)
    assert len(adapter.calls) == 2
    repair = adapter.calls[1]
    assert repair[:2] == adapter.calls[0]
    assert repair[2] == {"role": "assistant", "content": malformed}
    assert "Repair" in repair[3]["content"]


def test_repair_failure_reports_error_without_fabricating_feedback(coaching_context, scripted_adapter):
    adapter = scripted_adapter(["invalid first output", "invalid second output"])
    with pytest.raises(AIServiceError, match="invalid feedback after one repair") as error:
        OllamaCoachAgent(adapter).evaluate(coaching_context)
    assert len(adapter.calls) == 2
    assert "invalid second output" not in str(error.value)


def test_api_failure_does_not_trigger_content_repair(coaching_context, scripted_adapter):
    adapter = scripted_adapter([AIServiceError("Ollama Cloud authentication failed.")])
    with pytest.raises(AIServiceError, match="authentication"):
        OllamaCoachAgent(adapter).evaluate(coaching_context)
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("category", ["truncated", "reasoning_only", "empty_content"])
def test_incomplete_generation_recovers_once_with_bounded_budget(coaching_context, scripted_adapter, category):
    adapter = scripted_adapter([
        AIServiceError("Unusable final answer", category=category), json.dumps(FEEDBACK),
    ])
    result = OllamaCoachAgent(adapter).evaluate(coaching_context)
    assert result == CoachFeedback.model_validate(FEEDBACK)
    assert [options["max_tokens"] for options in adapter.options] == [8192, 8192]
    assert all(options["json_mode"] for options in adapter.options)
    assert adapter.calls[0] == adapter.calls[1]


def test_truncation_recovery_exhaustion_never_fabricates_feedback(coaching_context, scripted_adapter):
    adapter = scripted_adapter([AIServiceError("Token limit reached", category="truncated")] * 2)
    with pytest.raises(AIServiceError) as error:
        OllamaCoachAgent(adapter).evaluate(coaching_context)
    assert error.value.category == "truncated"
    assert len(adapter.calls) == 2


def test_truncation_and_schema_repair_share_one_recovery_allowance(coaching_context, scripted_adapter):
    adapter = scripted_adapter([
        AIServiceError("Token limit reached", category="truncated"), "{broken json",
    ])
    with pytest.raises(AIServiceError, match="invalid feedback"):
        OllamaCoachAgent(adapter).evaluate(coaching_context)
    assert len(adapter.calls) == 2


def test_coach_parse_diagnostics_are_separate_from_api_response_failures(coaching_context, scripted_adapter):
    adapter = scripted_adapter(["{invalid json", json.dumps(FEEDBACK)])
    events = []
    OllamaCoachAgent(adapter, diagnostics=events.append).evaluate(coaching_context)
    assert events == [
        {"stage": "coach_feedback", "validation_failure_category": "invalid_json",
         "json_error_location": {"line": 1, "column": 2}},
        {"stage": "coach_feedback", "validation_failure_category": None},
    ]
    assert "invalid json" not in json.dumps(events)


def test_acknowledged_limitation_is_preserved_for_grounded_coaching(
    content, interviews, recommendations, scripted_adapter
):
    session = interviews.create_session("maryam")
    session = interviews.record_student_message(session, "How much business cash is available and due?")
    session = interviews.record_client_response(session, "QAR 25,000 available, with QAR 40,000 due.")
    session = interviews.end_interview(session)
    session = recommendations.submit_summary(session, "A QAR 15,000 timing gap needs a contingency.")
    justification = "Track overdue invoices. This service supplies no financing."
    session = recommendations.submit_recommendations(session, [ProductRecommendation(
        product_id="business-cash-management", justification=justification,
    )])
    expected = {
        "what_went_well": ["You acknowledged that cash management supplies no financing."],
        "what_was_missed": ["Acceptable financing preferences were not explored."],
        "how_to_improve": ["Ask which financing arrangements the client would accept."],
    }
    adapter = scripted_adapter([json.dumps(expected)])
    result = OllamaCoachAgent(adapter).evaluate(build_coaching_context(session, content))
    evidence = json.loads(adapter.calls[0][1]["content"])
    assert evidence["recommendations"] == [{"product_id": "business-cash-management", "justification": justification}]
    assert evidence["transcript"] == session.model_dump(mode="json")["transcript"]
    assert "do not claim the student omitted" in adapter.calls[0][0]["content"]
    assert "Check all three sections for contradictory assessments" in adapter.calls[0][0]["content"]
    assert result.model_dump(mode="json") == expected


def test_json_mode_does_not_accept_missing_feedback_sections(coaching_context, scripted_adapter):
    events = []
    adapter = scripted_adapter(['{"unexpected": "private-output-marker"}', json.dumps(FEEDBACK)])
    result = OllamaCoachAgent(adapter, diagnostics=events.append).evaluate(coaching_context)
    assert result == CoachFeedback.model_validate(FEEDBACK)
    assert events[0]["validation_failure_category"] == "invalid_schema"
    assert {item["field"] for item in events[0]["schema_errors"]} == {
        "what_went_well", "what_was_missed", "how_to_improve", "other",
    }
    assert "private-output-marker" not in json.dumps(events)
