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
