from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from bank_simulator.models import (
    InterviewMessage,
    InterviewSession,
    InterviewStatus,
    MessageRole,
    ProductRecommendation,
)


def test_create_and_select_client(interviews):
    draft = interviews.create_session()
    assert draft.status is InterviewStatus.DRAFT
    assert draft.client_id is None
    assert draft.transcript == ()

    session = interviews.select_client(draft, "maryam")
    assert session.status is InterviewStatus.ACTIVE
    assert session.client_id == "maryam"
    assert session.session_id == draft.session_id
    assert draft.client_id is None
    assert interviews.create_session("mohamed").session_id != session.session_id


def test_unknown_client_is_rejected(interviews):
    with pytest.raises(ValueError, match="Unknown client ID 'unknown'"):
        interviews.create_session("unknown")


def test_transcript_records_supplied_messages_in_order(interviews):
    session = interviews.create_session("maryam")
    assert interviews.get_history(session) == ()

    session = interviews.record_student_message(session, "  When do customers pay?\n")
    after_question = session
    session = interviews.record_client_response(session, "Usually after the due date.")
    session = interviews.record_student_message(session, "What bills are due first?")
    history = interviews.get_history(session)

    assert [message.role for message in history] == [MessageRole.STUDENT, MessageRole.CLIENT, MessageRole.STUDENT]
    assert [message.content for message in history] == [
        "  When do customers pay?\n", "Usually after the due date.", "What bills are due first?",
    ]
    timestamps = [message.timestamp for message in history]
    assert timestamps == sorted(timestamps)
    assert all(timestamp.utcoffset() == timedelta(0) for timestamp in timestamps)
    assert len(interviews.get_history(after_question)) == 1


def test_serialized_session_validates_and_restores_original_state(completed_interview):
    assert InterviewSession.model_validate_json(completed_interview.model_dump_json()) == completed_interview


@pytest.mark.parametrize(
    ("client_id", "topic"),
    [("maryam", "Invoice payment timing"), ("mohamed", "Savings and irregular expenses")],
)
def test_client_context_is_for_the_selected_client(interviews, client_id, topic):
    session = interviews.create_session(client_id)
    session = interviews.record_student_message(session, "What would you like to discuss today?")
    context = interviews.build_client_context(session)
    assert session.client_id == context.client_profile.id == context.hidden_needs.client_id == client_id
    assert topic in {item.topic for item in context.hidden_needs.disclosure_topics}
    assert context.transcript == session.transcript
    assert "hidden_needs" not in session.model_dump()


def test_end_and_reset_interview(interviews, recommendations, completed_interview):
    completed = recommendations.submit_summary(completed_interview, "Mohamed is saving for certification.")
    completed = recommendations.submit_recommendations(
        completed, [ProductRecommendation(product_id="goal-saver-account", justification="Dated goal")]
    )
    assert completed.status is InterviewStatus.COMPLETED
    assert completed.transcript == completed_interview.transcript

    reset = interviews.reset_interview(completed)
    assert reset.status is InterviewStatus.ACTIVE
    assert reset.client_id == "mohamed"
    assert reset.session_id != completed.session_id
    assert reset.transcript == reset.selected_recommendations == ()
    assert reset.student_summary is None

    draft = interviews.create_session()
    reset_draft = interviews.reset_interview(draft)
    assert reset_draft.status is InterviewStatus.DRAFT
    assert reset_draft.session_id != draft.session_id


def test_selecting_another_client_requires_a_draft(interviews, completed_interview):
    for session, other_client in (
        (interviews.create_session("maryam"), "mohamed"),
        (completed_interview, "maryam"),
    ):
        with pytest.raises(ValueError, match="only be selected for a draft"):
            interviews.select_client(session, other_client)


def test_message_writes_and_finalization_require_active_session(interviews, completed_interview):
    for session in (interviews.create_session(), completed_interview):
        for record in (interviews.record_student_message, interviews.record_client_response):
            with pytest.raises(ValueError, match="requires an active interview"):
                record(session, "Hello")
        with pytest.raises(ValueError, match="requires an active interview"):
            interviews.end_interview(session)
        with pytest.raises(ValueError, match="requires an active interview"):
            interviews.build_client_context(session)


@pytest.mark.parametrize("method", ["record_student_message", "record_client_response"])
def test_blank_message_is_rejected(interviews, method):
    session = interviews.create_session("mohamed")
    with pytest.raises(ValidationError, match="non-whitespace"):
        getattr(interviews, method)(session, " \t\n")


def test_rehydrated_transcript_must_be_chronological():
    now = datetime.now(UTC)
    messages = (
        InterviewMessage(role=MessageRole.STUDENT, content="Question", timestamp=now),
        InterviewMessage(role=MessageRole.CLIENT, content="Answer", timestamp=now - timedelta(seconds=1)),
    )
    with pytest.raises(ValidationError, match="chronological order"):
        InterviewSession(client_id="maryam", transcript=messages, status=InterviewStatus.ACTIVE)


def test_rehydrated_active_interview_requires_a_client():
    with pytest.raises(ValidationError, match="requires a client"):
        InterviewSession(status=InterviewStatus.ACTIVE)
