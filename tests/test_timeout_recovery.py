"""Actual SDK and immutable web workflow, using an offline HTTP transport."""

import json

import httpx
from openai import OpenAI
from pydantic import SecretStr

from bank_simulator.agents.api_adapter import OllamaCloudAdapter
from bank_simulator.config import Settings
from bank_simulator.ui import controller
from bank_simulator.ui.controller import WebController, Workspace
from bank_simulator.ui.export import student_report


def _completion(text):
    return {"id": "offline", "object": "chat.completion", "created": 1,
            "model": "deepseek-v4.1-flash", "choices": [
                {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}},
            ]}


def test_mid_interview_sdk_timeout_preserves_snapshot_and_explicit_retry_counts_once(content, monkeypatch):
    outcomes = iter((_completion("I have QAR 1,200 set aside for emergencies."),
                     httpx.ReadTimeout("private-transport-detail synthetic-key"),
                     _completion("I need access the same day if an unexpected bill arrives.")))
    requests = []

    def transport(request):
        requests.append(request)
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(200, json=outcome)

    def create():
        sdk = OpenAI(base_url="https://ollama.com/v1", api_key="synthetic-key",
                     http_client=httpx.Client(transport=httpx.MockTransport(transport)))
        return OllamaCloudAdapter(Settings(ai_api_key=SecretStr("synthetic-key")),
                                  client=sdk, max_retries=0, diagnostics=controller._log_request_failure)

    monkeypatch.setattr(controller, "create_adapter", create)
    state = Workspace()
    ui = WebController(state, content)
    ui.start("mohamed")
    assert ui.send("How much emergency money is set aside?")
    snapshot = state.session
    question = "How quickly would you need access to that money?"
    assert not ui.send(question)
    assert state.session is snapshot and len(snapshot.transcript) == 2
    assert state.requests == len(requests) == 2
    assert state.failed_question == question and not state.busy
    assert "timed out" in state.error and "private-transport-detail" not in state.error
    report = json.loads(student_report(state.session, state.feedback, content))
    assert len(report["transcript"]) == 2 and report["coach_feedback"] is None
    assert all(message["content"] != question for message in report["transcript"])
    assert ui.send(state.failed_question)
    assert state.requests == len(requests) == 3
    assert state.session.transcript[:2] == snapshot.transcript
    assert [message.content for message in state.session.transcript].count(question) == 1
    assert len(state.session.transcript) == 4 and len(snapshot.transcript) == 2
    assert state.failed_question is state.error is None
    assert all(request.extensions["timeout"]["read"] == 60.0 for request in requests)


def test_web_adapter_keeps_automatic_retries_disabled(monkeypatch):
    options = {}
    monkeypatch.setattr(controller, "OllamaCloudAdapter", lambda **kwargs: options.update(kwargs))
    controller.create_adapter()
    assert options["max_retries"] == 0
    assert options["diagnostics"] is controller._log_request_failure


def test_cloud_failure_log_allowlists_metadata_and_ignores_successes(caplog):
    controller._log_request_failure({"validation_failure_category": None, "elapsed_seconds": 1.0})
    assert not caplog.records
    controller._log_request_failure({
        "validation_failure_category": "timeout", "elapsed_seconds": 60.648,
        "api_exception_type": "private-exception-detail", "api_key": "synthetic-key",
        "messages": "private-profile private-prompt", "reasoning": "private-reasoning",
        "model": "private-model-setting", "http_status": None,
    })
    assert "category=timeout" in caplog.text and "60.648" in caplog.text
    for marker in ("synthetic-key", "private-profile", "private-prompt", "private-reasoning",
                   "private-exception-detail", "private-model-setting"):
        assert marker not in caplog.text
