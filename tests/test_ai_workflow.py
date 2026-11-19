import json

import pytest

from bank_simulator.agents.api_adapter import AIServiceError
from bank_simulator.agents.client_agent import OllamaClientAgent
from bank_simulator.agents.coach_agent import OllamaCoachAgent
from bank_simulator.models import InterviewStatus, MessageRole, ProductRecommendation
from bank_simulator.services.ai_workflow import AIWorkflow


@pytest.mark.parametrize("client_id", ["maryam", "mohamed"])
def test_complete_workflow_preserves_snapshots_and_allows_unsuitable_choices(
    content, interviews, recommendations, scripted_adapter, client_id
):
    feedback_json = json.dumps({
        "what_went_well": [],
        "what_was_missed": ["The banking preference was not explored."],
        "how_to_improve": ["Ask about acceptable financing arrangements."],
    })
    adapter = scripted_adapter(["I would like to review my options.", "I can explain further.", feedback_json])
    workflow = AIWorkflow(content, OllamaClientAgent(adapter), OllamaCoachAgent(adapter))
    original = interviews.create_session(client_id)
    first = workflow.send_student_message(original, "What brings you in today?")
    second = workflow.send_student_message(first, "Could you say more about that?")
    assert original.transcript == ()
    assert len(first.transcript) == 2
    assert [item.role for item in second.transcript] == [
        MessageRole.STUDENT, MessageRole.CLIENT, MessageRole.STUDENT, MessageRole.CLIENT,
    ]
    assert list(second.transcript) == sorted(second.transcript, key=lambda message: message.timestamp)
    assert second.session_id == original.session_id
    ended = interviews.end_interview(second)
    assert ended.status is InterviewStatus.COMPLETED
    submitted = recommendations.submit_summary(ended, "A general review of options.")
    submitted = recommendations.submit_recommendations(submitted, [ProductRecommendation(
        product_id="business-flex-credit", justification="The name sounds flexible.",
    )])
    feedback = workflow.generate_feedback(submitted)
    assert feedback.what_was_missed
    coach_payload = json.loads(adapter.calls[-1][1]["content"])
    assert coach_payload["hidden_needs"]["client_id"] == client_id
    assert coach_payload["transcript"] == submitted.model_dump(mode="json")["transcript"]
    assert coach_payload["recommendations"][0]["product_id"] == "business-flex-credit"


def test_failed_turn_is_atomic_and_safe_to_retry(content, interviews, scripted_adapter):
    adapter = scripted_adapter([AIServiceError("Connection failed."), "A real caller-supplied response."])
    workflow = AIWorkflow(content, OllamaClientAgent(adapter), OllamaCoachAgent(adapter))
    original = interviews.create_session("maryam")
    with pytest.raises(AIServiceError):
        workflow.send_student_message(original, "Tell me about your business.")
    assert original.transcript == ()
    updated = workflow.send_student_message(original, "Tell me about your business.")
    assert len(updated.transcript) == 2


def test_existing_pending_question_gets_exactly_one_reply(content, interviews, scripted_adapter):
    adapter = scripted_adapter(["I can tell you about my business."])
    workflow = AIWorkflow(content, OllamaClientAgent(adapter), OllamaCoachAgent(adapter))
    pending = interviews.record_student_message(interviews.create_session("maryam"), "Tell me about your business.")
    with pytest.raises(ValueError, match="pending student message"):
        workflow.send_student_message(pending, "Another question")
    updated = workflow.respond_to_pending(pending)
    assert updated.transcript[0] == pending.transcript[0]
    assert len(updated.transcript) == 2
    with pytest.raises(ValueError, match="no pending"):
        workflow.respond_to_pending(updated)
    assert len(adapter.calls) == 1


def test_invalid_lifecycle_never_calls_api(content, interviews, scripted_adapter):
    adapter = scripted_adapter([])
    workflow = AIWorkflow(content, OllamaClientAgent(adapter), OllamaCoachAgent(adapter))
    draft = interviews.create_session()
    completed = interviews.end_interview(interviews.create_session("maryam"))
    for session in (draft, completed):
        with pytest.raises(ValueError, match="active interview"):
            workflow.send_student_message(session, "Hello")
        with pytest.raises(ValueError):
            workflow.generate_feedback(session)
    assert adapter.calls == []


def test_coach_failure_and_later_recovery_preserve_completed_interview(
    content, recommendations, completed_interview, scripted_adapter
):
    submitted = recommendations.submit_summary(completed_interview, "A certification savings goal.")
    submitted = recommendations.submit_recommendations(submitted, [ProductRecommendation(
        product_id="goal-saver-account", justification="Separate the dated goal from emergency money.",
    )])
    snapshot = submitted.model_dump_json()
    feedback = json.dumps({
        "what_went_well": ["You asked about the goal."],
        "what_was_missed": ["Liquidity needs require follow-up."],
        "how_to_improve": ["Ask how quickly emergency money is needed."],
    })
    adapter = scripted_adapter([
        AIServiceError("Token limit reached", category="truncated"),
        AIServiceError("Token limit reached", category="truncated"), feedback,
    ])
    workflow = AIWorkflow(content, OllamaClientAgent(adapter), OllamaCoachAgent(adapter))
    with pytest.raises(AIServiceError):
        workflow.generate_feedback(submitted)
    assert submitted.model_dump_json() == snapshot
    assert workflow.generate_feedback(submitted).what_went_well
    assert submitted.model_dump_json() == snapshot
    assert len(adapter.calls) == 3
