"""Offline interaction tests for the actual Streamlit entry point."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from bank_simulator.agents.api_adapter import AIServiceError
from bank_simulator.models import InterviewStatus
from bank_simulator.ui import controller


APP = Path(__file__).resolve().parents[1] / "app.py"
FEEDBACK = {
    "what_went_well": ["You asked about the client's priorities."],
    "what_was_missed": ["Follow up on unresolved affordability."],
    "how_to_improve": ["Ask which expenses can change from month to month."],
}


@pytest.fixture
def web(monkeypatch, scripted_adapter):
    adapter = scripted_adapter([])
    adapter.close = lambda: None
    constructions = []

    def create():
        constructions.append(True)
        return adapter

    monkeypatch.setattr(controller, "create_adapter", create)
    app = AppTest.from_file(str(APP), default_timeout=10).run()
    assert not app.exception
    return app, adapter, constructions


def _start(app, client="maryam"):
    app.button(key=f"start_{client}").click().run()
    assert not app.exception


def _end(app):
    app.button(key="end_interview").click().run()
    assert not app.exception


def _fill_submission(app, summary="A general banking review.", products=("business-flex-credit",), justification="My original reasoning."):
    app.text_area[0].set_value(summary)
    app.multiselect[0].set_value(list(products)).run()
    assert not app.exception
    for product_id in products:
        field = next(field for field in app.text_area if field.key.endswith(f"_why_{product_id}"))
        field.set_value(justification)
    next(button for button in app.button if button.label == "Submit & get coaching").click().run()
    assert not app.exception


def _visible(app):
    return "\n".join(str(element.value) for kind in ("text", "markdown", "caption", "info", "error", "subheader")
                     for element in app.get(kind))


def test_startup_public_profiles_catalogue_and_no_ai_initialization(web, content):
    app, adapter, constructions = web
    visible = _visible(app)
    assert "Maryam Al-Kuwari" in visible and "Mohamed Al-Ansari" in visible
    assert "fictional products" in visible
    assert "STEP 01" in visible and "Coach feedback" in visible
    assert len([expander for expander in app.expander if expander.label in {product.name for product in content.list_products()}]) == 5
    for product in content.list_products():
        for term in (*product.key_features, *product.eligibility_requirements, *product.limitations, *product.unsuitable_use_cases):
            assert term in visible
    assert "QAR 25,000" not in visible and "QAR 1,200" not in visible
    assert "question_patterns" not in visible and "Private reviewer reference" not in visible
    assert adapter.calls == [] and constructions == []


@pytest.mark.parametrize("client", ["maryam", "mohamed"])
def test_selection_uses_correct_client_without_requesting_an_opening_response(web, client):
    app, adapter, _ = web
    _start(app, client)
    state = app.session_state["workspace"]
    assert state.session.client_id == client
    assert state.session.status is InterviewStatus.ACTIVE
    assert state.session.transcript == ()
    assert len(app.chat_input) == 1
    assert adapter.calls == []
    assert "QAR 25,000" not in _visible(app) and "QAR 1,200" not in _visible(app)


def test_multiturn_chat_survives_reruns_without_duplicate_requests(web):
    app, adapter, constructions = web
    adapter.responses.extend(["I run a distribution business.", "It has regular transactions."])
    _start(app)
    original = app.session_state["workspace"].session
    app.chat_input[0].set_value("Tell me about your business.").run()
    first = app.session_state["workspace"].session
    app.run()
    app.chat_input[0].set_value("Could you tell me more about that?").run()
    app.run()
    state = app.session_state["workspace"]
    assert not app.exception
    assert original.transcript == () and len(first.transcript) == 2
    assert len(state.session.transcript) == len(app.chat_message) == 4
    assert len(adapter.calls) == len(constructions) == state.requests == 2
    assert [message["role"] for message in adapter.calls[-1]] == ["system", "user", "assistant", "user"]
    assert "maryam" in adapter.calls[-1][0]["content"] and "Mohamed" not in adapter.calls[-1][0]["content"]


def test_failed_question_is_preserved_and_retried_once(web):
    app, adapter, _ = web
    adapter.responses.extend([AIServiceError("The AI request timed out."), "I run a business."])
    _start(app)
    original = app.session_state["workspace"].session
    app.chat_input[0].set_value("Tell me about your business.").run()
    assert app.session_state["workspace"].session == original
    assert app.session_state["workspace"].failed_question == "Tell me about your business."
    app.run()
    assert len(adapter.calls) == 1
    app.button(key="retry_question").click().run()
    app.run()
    state = app.session_state["workspace"]
    assert not app.exception
    assert len(state.session.transcript) == 2 and len(adapter.calls) == 2
    assert state.failed_question is None and state.error is None


def test_timeout_after_a_valid_turn_preserves_history_and_only_retries_on_click(web):
    app, adapter, _ = web
    adapter.responses.extend(["I have QAR 1,200 in emergency savings.",
                              AIServiceError("The AI request timed out. Please try again."),
                              "I need access the same day."])
    _start(app, "mohamed")
    app.chat_input[0].set_value("How much emergency money is set aside?").run()
    snapshot = app.session_state["workspace"].session
    question = "How quickly would you need access to that money?"
    app.chat_input[0].set_value(question).run()
    app.run()
    state = app.session_state["workspace"]
    assert state.session == snapshot and len(app.chat_message) == 2
    assert state.requests == len(adapter.calls) == 2
    assert state.failed_question == question and "timed out" in _visible(app)
    app.button(key="retry_question").click().run()
    app.run()
    state = app.session_state["workspace"]
    assert not app.exception
    assert state.requests == len(adapter.calls) == 3
    assert len(app.chat_message) == len(state.session.transcript) == 4
    assert state.session.transcript[:2] == snapshot.transcript
    assert [message.content for message in state.session.transcript].count(question) == 1


@pytest.mark.parametrize("kind", ["summary", "products", "justification"])
def test_submission_rejects_missing_fields_without_calling_coach(web, kind):
    app, adapter, _ = web
    _start(app)
    _end(app)
    snapshot = app.session_state["workspace"].session
    _fill_submission(app, summary=" " if kind == "summary" else "A needs summary.",
                     products=() if kind == "products" else ("business-flex-credit",),
                     justification=" " if kind == "justification" else "My reasoning.")
    assert app.error
    assert app.session_state["workspace"].session == snapshot
    assert adapter.calls == []


def test_complete_workflow_accepts_unsuitable_multiple_products_and_keeps_exact_wording(web):
    app, adapter, _ = web
    adapter.responses.extend(["I prefer Sharia-compliant arrangements.", json.dumps(FEEDBACK)])
    _start(app)
    app.chat_input[0].set_value("What financing arrangements would you accept?").run()
    _end(app)
    summary, justification = "  My needs summary.\n", "  My reasoning with spacing.\n"
    _fill_submission(app, summary=summary, products=("business-flex-credit", "business-cash-management"), justification=justification)
    state = app.session_state["workspace"]
    assert state.stage == 4 and state.feedback is not None
    assert state.session.student_summary == summary
    assert len(state.session.selected_recommendations) == 2
    assert all(choice.justification == justification for choice in state.session.selected_recommendations)
    for title in ("What went well", "What was missed", "How to improve"):
        assert title in _visible(app)
    context = json.loads(adapter.calls[-1][1]["content"])
    assert context["client_profile"]["id"] == context["hidden_needs"]["client_id"] == "maryam"
    assert context["student_summary"] == summary
    assert context["recommendations"] == [choice.model_dump() for choice in state.session.selected_recommendations]
    app.run()
    app.run()
    assert len(adapter.calls) == state.requests == 2


def test_failed_coach_preserves_submission_and_retries_only_on_click(web):
    app, adapter, _ = web
    adapter.responses.extend([AIServiceError("Could not connect to Ollama Cloud."), json.dumps(FEEDBACK)])
    _start(app, "mohamed")
    _end(app)
    _fill_submission(app, products=("goal-saver-account",))
    snapshot = app.session_state["workspace"].session.model_dump_json()
    assert app.session_state["workspace"].feedback is None
    app.run()
    assert len(adapter.calls) == 1
    assert app.session_state["workspace"].session.model_dump_json() == snapshot
    app.button(key="retry_coaching").click().run()
    app.run()
    assert app.session_state["workspace"].feedback is not None
    assert len(adapter.calls) == 2
    assert app.session_state["workspace"].session.model_dump_json() == snapshot


def test_restart_and_client_switch_clear_old_work_and_disclosure(web):
    app, adapter, _ = web
    adapter.responses.extend(["I prefer Sharia-compliant banking.", "I want to organize my finances."])
    _start(app)
    app.chat_input[0].set_value("What financing preferences do you have?").run()
    previous = app.session_state["workspace"].session
    app.button(key="restart").click().run()
    restarted = app.session_state["workspace"].session
    assert restarted.client_id == "maryam" and restarted.session_id != previous.session_id
    assert restarted.transcript == () and app.session_state["workspace"].requests == 0
    app.button(key="choose_another").click().run()
    _start(app, "mohamed")
    app.chat_input[0].set_value("Tell me about yourself.").run()
    state = app.session_state["workspace"]
    assert state.session.client_id == "mohamed"
    assert state.feedback is None and state.failed_question is None
    assert "Maryam" not in json.dumps(adapter.calls[-1])
    assert "Sharia-compliant banking" not in json.dumps(adapter.calls[-1])


def test_revision_prefills_original_submission_without_a_model_request(web):
    app, adapter, _ = web
    adapter.responses.append(json.dumps(FEEDBACK))
    _start(app)
    _end(app)
    _fill_submission(app, summary="  Original summary.\n", justification="  Original reason.\n")
    app.button(key="revise_submission").click().run()
    assert app.session_state["workspace"].stage == 3
    assert app.text_area[0].value == "  Original summary.\n"
    assert app.multiselect[0].value == ["business-flex-credit"]
    assert next(field for field in app.text_area if field.key.endswith("_why_business-flex-credit")).value == "  Original reason.\n"
    assert len(adapter.calls) == 1


def test_browser_sessions_do_not_share_interviews(web):
    app, adapter, _ = web
    adapter.responses.append("I run a business.")
    _start(app)
    app.chat_input[0].set_value("Tell me about your business.").run()
    other = AppTest.from_file(str(APP), default_timeout=10).run()
    assert not other.exception
    assert other.session_state["workspace"].session is None
    assert app.session_state["workspace"].session.client_id == "maryam"
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("products", [
    ("business-flex-credit",), ("goal-saver-account", "everyday-access-account"),
])
def test_only_selected_products_have_immediately_visible_justification_fields(web, products):
    app, adapter, _ = web
    _start(app)
    _end(app)
    assert [field.label for field in app.text_area] == ["Financial needs summary"]
    app.multiselect[0].set_value(list(products)).run()
    assert not app.exception
    assert len(app.text_area) == 1 + len(products)
    assert {field.key.rsplit("_why_", 1)[-1] for field in app.text_area[1:]} == set(products)
    assert not any(expander.label.startswith("Justification") for expander in app.expander)
    assert "Briefly explain why this product fits the client's needs. Mention any important limitations." in _visible(app)
    assert adapter.calls == []


def test_one_word_justification_is_valid_without_a_minimum_word_count(web):
    app, adapter, _ = web
    adapter.responses.append(json.dumps(FEEDBACK))
    _start(app, "mohamed")
    _end(app)
    _fill_submission(app, products=("goal-saver-account",), justification="Fits.")
    state = app.session_state["workspace"]
    assert state.stage == 4 and state.feedback is not None
    assert state.session.selected_recommendations[0].justification == "Fits."
    assert len(adapter.calls) == 1


def test_missing_justification_has_a_product_specific_inline_error(web):
    app, adapter, _ = web
    _start(app)
    _end(app)
    app.multiselect[0].set_value(["goal-saver-account", "everyday-access-account"]).run()
    app.text_area[0].set_value("A needs summary.")
    next(field for field in app.text_area if field.key.endswith("_why_goal-saver-account")).set_value("For a dated goal.")
    next(button for button in app.button if button.label == "Submit & get coaching").click().run()
    assert not app.exception
    assert len(app.error) == 1
    assert app.error[0].value == "Add a brief justification for Everyday Access Account."
    assert app.session_state["workspace"].session.student_summary is None
    assert adapter.calls == []


def test_changing_product_selections_preserves_summary_and_hidden_drafts(web):
    app, adapter, _ = web
    _start(app)
    _end(app)
    app.multiselect[0].set_value(["goal-saver-account"]).run()
    app.text_area[0].set_value("  Draft summary.\n")
    next(field for field in app.text_area if field.key.endswith("_why_goal-saver-account")).set_value("  First draft.\n")
    app.multiselect[0].set_value(["goal-saver-account", "everyday-access-account"]).run()
    assert app.text_area[0].value == "  Draft summary.\n"
    assert next(field for field in app.text_area if field.key.endswith("_why_goal-saver-account")).value == "  First draft.\n"
    next(field for field in app.text_area if field.key.endswith("_why_everyday-access-account")).set_value("  Second draft.\n")
    app.multiselect[0].set_value(["everyday-access-account"]).run()
    assert len(app.text_area) == 2
    app.run()
    app.multiselect[0].set_value([]).run()
    assert len(app.text_area) == 1
    app.multiselect[0].set_value(["goal-saver-account", "everyday-access-account"]).run()
    assert not app.exception
    assert app.text_area[0].value == "  Draft summary.\n"
    assert next(field for field in app.text_area if field.key.endswith("_why_goal-saver-account")).value == "  First draft.\n"
    assert next(field for field in app.text_area if field.key.endswith("_why_everyday-access-account")).value == "  Second draft.\n"
    assert adapter.calls == []


def test_deselected_product_draft_is_excluded_from_coaching_and_export(web, content):
    from bank_simulator.ui.export import student_report

    app, adapter, _ = web
    adapter.responses.append(json.dumps(FEEDBACK))
    _start(app)
    _end(app)
    app.multiselect[0].set_value(["goal-saver-account", "everyday-access-account"]).run()
    app.text_area[0].set_value("The student's actual summary.")
    next(field for field in app.text_area if field.key.endswith("_why_goal-saver-account")).set_value("Retained selected explanation.")
    hidden_draft = "A deselected draft that must not be submitted."
    next(field for field in app.text_area if field.key.endswith("_why_everyday-access-account")).set_value(hidden_draft)
    app.multiselect[0].set_value(["goal-saver-account"]).run()
    next(button for button in app.button if button.label == "Submit & get coaching").click().run()
    assert not app.exception
    state = app.session_state["workspace"]
    assert [choice.product_id for choice in state.session.selected_recommendations] == ["goal-saver-account"]
    assert state.justification_drafts["everyday-access-account"] == hidden_draft
    assert hidden_draft not in json.dumps(adapter.calls)
    assert hidden_draft not in student_report(state.session, state.feedback, content)
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("action", ["restart", "choose_another"])
def test_starting_a_fresh_interview_clears_justification_drafts(web, action):
    app, adapter, _ = web
    _start(app)
    _end(app)
    app.multiselect[0].set_value(["goal-saver-account"]).run()
    next(field for field in app.text_area if field.key.endswith("_why_goal-saver-account")).set_value("Previous client's draft.").run()
    assert app.session_state["workspace"].justification_drafts
    app.button(key=action).click().run()
    if action == "choose_another":
        _start(app, "mohamed")
    assert app.session_state["workspace"].justification_drafts == {}
    _end(app)
    app.multiselect[0].set_value(["goal-saver-account"]).run()
    assert next(field for field in app.text_area if field.key.endswith("_why_goal-saver-account")).value == ""
    assert adapter.calls == []
