import json
import traceback

import httpx
import pytest
from openai import OpenAI
from pydantic import SecretStr

from bank_simulator.agents.api_adapter import AIServiceError, OllamaCloudAdapter
from bank_simulator.config import Settings


def completion(content="A supplied test response.", *, choices=True, finish_reason="stop"):
    return {
        "id": "test-completion", "object": "chat.completion", "created": 1,
        "model": "deepseek-v4.1-flash",
        "choices": [{"index": 0, "finish_reason": finish_reason,
                     "message": {"role": "assistant", "content": content}}] if choices else [],
    }


@pytest.fixture
def make_adapter(monkeypatch):
    adapters = []
    monkeypatch.setattr("bank_simulator.agents.api_adapter.time.sleep", lambda _: None)

    def build(outcomes, *, max_retries=1):
        requests = []
        responses = iter(outcomes)

        def handle(request):
            requests.append(request)
            outcome = next(responses)
            if isinstance(outcome, Exception):
                raise outcome
            status, payload = outcome
            return httpx.Response(status, json=payload)

        sdk = OpenAI(
            base_url="https://ollama.com/v1", api_key="synthetic-key",
            http_client=httpx.Client(transport=httpx.MockTransport(handle)),
        )
        adapter = OllamaCloudAdapter(
            Settings(ai_api_key=SecretStr("synthetic-key")), client=sdk, max_retries=max_retries,
        )
        adapters.append(adapter)
        return adapter, requests

    yield build
    for adapter in adapters:
        adapter.close()


def test_endpoint_model_and_successful_response(make_adapter):
    adapter, requests = make_adapter([(200, completion())])
    assert adapter.complete([{"role": "user", "content": "Hello"}]) == "A supplied test response."
    assert str(requests[0].url) == "https://ollama.com/v1/chat/completions"
    assert json.loads(requests[0].content)["model"] == "deepseek-v4.1-flash"
    assert json.loads(requests[0].content)["messages"] == [{"role": "user", "content": "Hello"}]
    assert requests[0].extensions["timeout"]["read"] == 60.0
    assert adapter.request_count == 1
    assert adapter.response_models == {"deepseek-v4.1-flash"}


def test_constructor_loads_environment_and_allows_model_change(monkeypatch):
    captured = {}

    def sdk_constructor(**options):
        captured.update(options)
        return object()

    monkeypatch.setattr("bank_simulator.agents.api_adapter.OpenAI", sdk_constructor)
    monkeypatch.setenv("AI_API_URL", "https://ollama.com/v1")
    monkeypatch.setenv("AI_API_KEY", "synthetic-environment-key")
    monkeypatch.setenv("AI_MODEL", "another-cloud-model")
    adapter = OllamaCloudAdapter()
    assert captured["base_url"] == "https://ollama.com/v1"
    assert captured["api_key"] == "synthetic-environment-key"
    assert captured["max_retries"] == 0
    assert adapter.model == "another-cloud-model"


@pytest.mark.parametrize("payload", [
    completion(""), completion(" \n"), completion(None), completion(choices=False), {},
    {"choices": {"unexpected": "shape"}},
])
def test_empty_responses_are_rejected(make_adapter, payload):
    adapter, _ = make_adapter([(200, payload)])
    with pytest.raises(AIServiceError, match="empty response|no response choices"):
        adapter.complete([])
    assert adapter.request_count == 1


@pytest.mark.parametrize("status, message", [(401, "authentication"), (403, "authentication"),
                                          (404, "unavailable"), (400, "rejected")])
def test_permanent_errors_are_sanitized_without_retry(make_adapter, status, message, caplog):
    adapter, _ = make_adapter([(status, {"error": {"message": "synthetic-key"}})])
    with pytest.raises(AIServiceError, match=message) as error:
        adapter.complete([])
    assert adapter.request_count == 1
    assert "synthetic-key" not in "".join(traceback.format_exception(error.value))
    assert "synthetic-key" not in caplog.text


@pytest.mark.parametrize("status", [408, 409, 429, 500, 503])
def test_transient_status_retries_once_then_succeeds(make_adapter, status):
    adapter, requests = make_adapter([(status, {"error": "transient"}), (200, completion())])
    assert adapter.complete([]) == "A supplied test response."
    assert adapter.request_count == len(requests) == 2


@pytest.mark.parametrize("failure, message", [
    (httpx.ReadTimeout("synthetic-key"), "timed out"),
    (httpx.ConnectError("synthetic-key"), "connect"),
])
def test_transport_failures_are_bounded_and_masked(make_adapter, failure, message):
    adapter, requests = make_adapter([failure, failure])
    with pytest.raises(AIServiceError, match=message) as error:
        adapter.complete([])
    assert adapter.request_count == len(requests) == 2
    assert "synthetic-key" not in "".join(traceback.format_exception(error.value))


def test_exhausted_rate_limit_has_bounded_attempts(make_adapter):
    adapter, requests = make_adapter([(429, {"error": "synthetic-key"})] * 3, max_retries=2)
    with pytest.raises(AIServiceError, match="rate limit"):
        adapter.complete([])
    assert adapter.request_count == len(requests) == 3


def test_smoke_mode_disables_transient_retry(make_adapter):
    adapter, _ = make_adapter([(503, {"error": "unavailable"})], max_retries=0)
    with pytest.raises(AIServiceError, match="temporarily unavailable"):
        adapter.complete([])
    assert adapter.request_count == 1


def test_incomplete_response_and_echoed_credentials_are_rejected(make_adapter):
    for payload in (completion("Partial", finish_reason="length"), completion("synthetic-key")):
        adapter, _ = make_adapter([(200, payload)])
        with pytest.raises(AIServiceError):
            adapter.complete([])


def test_successful_api_calls_do_not_log_credentials(make_adapter, caplog):
    adapter, _ = make_adapter([(200, completion())])
    with caplog.at_level("INFO"):
        adapter.complete([])
    assert "synthetic-key" not in caplog.text


@pytest.mark.parametrize("options", [{"max_retries": -1}, {"max_retries": 3}, {"timeout": 0}, {"timeout": 121}])
def test_invalid_retry_and_timeout_options_are_rejected(options):
    with pytest.raises(ValueError):
        OllamaCloudAdapter(Settings(ai_api_key=SecretStr("synthetic-key")), **options)
