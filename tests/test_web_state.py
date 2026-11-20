"""Offline limits, failure safety, and allowlisted student export checks."""

import json
import tomllib
from pathlib import Path

import pytest

from bank_simulator.agents.api_adapter import AIServiceError
from bank_simulator.models import CoachFeedback, ProductRecommendation
from bank_simulator.ui import controller
from bank_simulator.ui.controller import (
    MAX_MESSAGE_CHARS, MAX_QUESTIONS, MAX_REQUESTS, WebController, Workspace,
)
from bank_simulator.ui.export import student_report


FEEDBACK = CoachFeedback(what_went_well=("You explored the goal.",), what_was_missed=(), how_to_improve=())


@pytest.fixture
def action(content, monkeypatch, scripted_adapter):
    state = Workspace()
    ui = WebController(state, content)
    ui.start("mohamed")
    adapter = scripted_adapter([])
    adapter.close = lambda: None
    monkeypatch.setattr(controller, "create_adapter", lambda: adapter)
    return ui, adapter


def _submit(ui):
    ui.end()
    ui.submit("A dated goal.", [ProductRecommendation(product_id="goal-saver-account", justification="For certification.")])


def test_request_budget_counts_failures_and_reserves_two_generations_for_coaching(action):
    ui, adapter = action
    ui.state.requests = MAX_REQUESTS - 3
    adapter.responses.extend([AIServiceError("Connection failed."), "{broken json", FEEDBACK.model_dump_json()])
    assert not ui.send("What are you saving for?")
    assert ui.state.requests == MAX_REQUESTS - 2
    assert not ui.send("A different question?")
    assert len(adapter.calls) == 1
    _submit(ui)
    assert ui.coach()
    assert ui.state.requests == MAX_REQUESTS
    assert len(adapter.calls) == 3
    assert not ui.coach()
    assert len(adapter.calls) == 3


def test_recovery_cannot_exceed_request_budget(action):
    ui, adapter = action
    _submit(ui)
    snapshot = ui.state.session
    ui.state.requests = MAX_REQUESTS - 1
    adapter.responses.append(AIServiceError("No final answer.", category="empty_content"))
    assert not ui.coach()
    assert ui.state.requests == MAX_REQUESTS
    assert len(adapter.calls) == 1 and ui.state.session == snapshot
    assert "request limit" in ui.state.error
    assert not ui.coach() and len(adapter.calls) == 1


def test_question_limit_blocks_another_turn_but_allows_submission(action):
    ui, adapter = action
    for _ in range(MAX_QUESTIONS):
        ui.state.session = ui.interviews.record_student_message(ui.state.session, "A question?")
        ui.state.session = ui.interviews.record_client_response(ui.state.session, "A supplied answer.")
    assert not ui.send("One more question?")
    assert adapter.calls == []
    _submit(ui)
    assert ui.state.session.selected_recommendations


@pytest.mark.parametrize("message", [" ", "x" * (MAX_MESSAGE_CHARS + 1)])
def test_invalid_question_does_not_consume_budget(action, message):
    ui, adapter = action
    assert not ui.send(message)
    assert ui.state.requests == 0 and adapter.calls == []


def test_unknown_products_are_rejected_atomically_without_changing_submission(action):
    ui, adapter = action
    ui.end()
    original = ui.state.session
    with pytest.raises(ValueError, match="Unknown product"):
        ui.submit("Valid summary.", [ProductRecommendation(product_id="unknown", justification="A reason.")])
    assert ui.state.session == original
    assert adapter.calls == []


def test_busy_actions_cannot_duplicate_or_reset_an_inflight_request(action):
    ui, adapter = action
    original = ui.state.session
    ui.state.busy = True
    assert not ui.send("A second message?")
    ui.start("maryam")
    ui.choose_another()
    ui.end()
    assert ui.state.session == original and adapter.calls == []
    assert ui.state.error is None


@pytest.mark.parametrize("failure", [ValueError("private-configuration-marker"), RuntimeError("private-sdk-marker")])
def test_unexpected_errors_do_not_render_private_details_and_allow_recovery(action, failure):
    ui, adapter = action
    adapter.responses.extend([failure, "I am saving toward certification."])
    snapshot = ui.state.session
    assert not ui.send("What are you saving for?")
    assert "private-" not in ui.state.error
    assert not ui.state.busy and ui.state.session == snapshot
    assert ui.send(ui.state.failed_question)
    assert len(ui.state.session.transcript) == 2 and len(adapter.calls) == 2


@pytest.mark.parametrize("client_id", ["maryam", "mohamed"])
def test_student_export_contains_only_observed_work_and_public_identity(content, interviews, recommendations, client_id):
    session = interviews.create_session(client_id)
    session = interviews.record_student_message(session, "  What brings you in?\n")
    session = interviews.record_client_response(session, "I would like to review my banking.")
    session = interviews.end_interview(session)
    session = recommendations.submit_summary(session, "  My exact summary.\n")
    session = recommendations.submit_recommendations(session, [ProductRecommendation(
        product_id="business-flex-credit", justification="  My exact reason.\n",
    )])
    report_text = student_report(session, FEEDBACK, content)
    report = json.loads(report_text)
    assert report["client"] == content.get_client(client_id).model_dump(mode="json")
    assert report["transcript"] == session.model_dump(mode="json")["transcript"]
    assert report["student_summary"] == "  My exact summary.\n"
    assert report["recommendations"][0]["justification"] == "  My exact reason.\n"
    assert report["coach_feedback"] == FEEDBACK.model_dump(mode="json")
    assert set(report) == {"report_type", "session_id", "status", "client", "transcript", "student_summary", "recommendations", "coach_feedback"}
    _, private = content.get_private_client(client_id)
    for fact in private.private_financial_facts:
        assert fact not in report_text
    for forbidden in ("hidden_needs", "question_patterns", "discovery_expectations", "private_financial_facts", "API_KEY", "reasoning", "system_prompt"):
        assert forbidden not in report_text
    assert json.loads(student_report(session, None, content))["coach_feedback"] is None


def test_web_configuration_disables_static_serving_and_overlapping_fast_reruns():
    config = Path(__file__).resolve().parents[1] / ".streamlit/config.toml"
    values = tomllib.loads(config.read_text())
    assert values["server"]["enableStaticServing"] is False
    assert values["runner"]["fastReruns"] is False
    assert values["client"]["showErrorDetails"] == "none"
    assert values["client"]["toolbarMode"] == "viewer"
