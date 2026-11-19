"""Small OpenAI SDK adapter for Ollama Cloud with bounded, sanitized failures."""

import re
import time
from collections.abc import Callable, Sequence
from typing import Protocol, cast

from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError, OpenAI
from openai.types.chat import ChatCompletionMessageParam

from ..config import Settings, load_settings


class AIServiceError(RuntimeError):
    """An AI request failed. Messages are safe to display to the user."""

    def __init__(self, message: str, *, category: str = "api_error") -> None:
        super().__init__(message)
        self.category = category


DiagnosticSink = Callable[[dict[str, object]], None]


def _token_usage(response: object) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    result = {}
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, field, None)
        if type(value) is int and value >= 0:
            result[field] = value
    reasoning = getattr(getattr(usage, "completion_tokens_details", None), "reasoning_tokens", None)
    if type(reasoning) is int and reasoning >= 0:
        result["reasoning_tokens"] = reasoning
    return result


class ChatAdapter(Protocol):
    def complete(
        self, messages: Sequence[ChatCompletionMessageParam], *, max_tokens: int = 2048,
        temperature: float = 0.3, json_mode: bool = False,
    ) -> str:
        """Return a nonempty assistant response or raise AIServiceError."""
        ...


class OllamaCloudAdapter:
    """Share one SDK client across both agents within an application lifecycle."""

    def __init__(
        self, settings: Settings | None = None, *, client: OpenAI | None = None,
        timeout: float = 60.0, max_retries: int = 1,
        diagnostics: DiagnosticSink | None = None,
    ) -> None:
        settings = (settings or load_settings()).require_ai_configuration()
        if not 0 <= max_retries <= 2:
            raise ValueError("max_retries must be between zero and two.")
        if not 0 < timeout <= 120:
            raise ValueError("timeout must be greater than zero and at most 120 seconds.")
        self.model = settings.ai_model
        self.request_count = 0
        self.response_models: set[str] = set()
        self.token_usage: dict[str, int] = {}
        self._key = settings.ai_api_key.get_secret_value()
        self._max_retries = max_retries
        self._diagnostics = diagnostics
        # Disable SDK retries so each counted attempt has exactly one HTTP request.
        self._client = client.with_options(timeout=timeout, max_retries=0) if client else OpenAI(
            base_url=settings.ai_api_url, api_key=self._key, timeout=timeout, max_retries=0,
        )

    def complete(
        self, messages: Sequence[ChatCompletionMessageParam], *, max_tokens: int = 2048,
        temperature: float = 0.3, json_mode: bool = False,
    ) -> str:
        for attempt in range(self._max_retries + 1):
            self.request_count += 1
            try:
                response_format = {"response_format": {"type": "json_object"}} if json_mode else {}
                response = self._client.chat.completions.create(
                    model=self.model, messages=list(messages), max_tokens=max_tokens,
                    temperature=temperature, **response_format,
                )
            except APITimeoutError:
                self._report_exception("APITimeoutError", "timeout", max_tokens)
                error = "The AI request timed out. Please try again."
            except APIConnectionError:
                self._report_exception("APIConnectionError", "connection", max_tokens)
                error = "Could not connect to Ollama Cloud. Please try again."
            except APIStatusError as exc:
                self._report_exception(type(exc).__name__, "http_error", max_tokens, exc.status_code)
                if exc.status_code in (401, 403):
                    raise AIServiceError("Ollama Cloud authentication failed. Check AI_API_KEY and access.") from None
                if exc.status_code == 404:
                    raise AIServiceError("The configured model or API endpoint is unavailable.") from None
                if exc.status_code not in (408, 409, 429) and exc.status_code < 500:
                    raise AIServiceError("Ollama Cloud rejected the AI request. Check configuration.") from None
                error = "Ollama Cloud is temporarily unavailable. Please try again."
                if exc.status_code == 429:
                    error = "Ollama Cloud rate limit reached. Please try again later."
            except APIError as exc:
                self._report_exception(type(exc).__name__, "invalid_api_response", max_tokens)
                raise AIServiceError("Ollama Cloud returned an invalid API response.") from None
            else:
                metadata = self._response_metadata(response, max_tokens)
                for field, count in cast(dict[str, int], metadata["usage"]).items():
                    self.token_usage[field] = self.token_usage.get(field, 0) + count
                reported_model = metadata["model"]
                if isinstance(reported_model, str):
                    self.response_models.add(reported_model)
                choices = getattr(response, "choices", None)
                if not isinstance(choices, list) or not choices:
                    self._reject(metadata, "missing_choices", "Ollama Cloud returned no response choices.")
                choice = choices[0]
                if getattr(choice, "finish_reason", None) == "length":
                    self._reject(metadata, "truncated", "Ollama Cloud reached the completion token limit before finishing.")
                if getattr(choice, "finish_reason", None) != "stop":
                    self._reject(metadata, "unsupported_finish", "Ollama Cloud returned an incomplete or unsupported response.")
                content = getattr(getattr(choice, "message", None), "content", None)
                if content is not None and not isinstance(content, str):
                    self._reject(metadata, "unsupported_content", "Ollama Cloud returned an unsupported content type.")
                if not content or not content.strip():
                    category = "reasoning_only" if metadata["reasoning_fields_present"] else "empty_content"
                    self._reject(metadata, category, "Ollama Cloud returned an empty response without a final answer.")
                if self._key in content:
                    self._reject(metadata, "sensitive_content", "The AI response contained sensitive configuration and was rejected.")
                if self._diagnostics:
                    self._diagnostics(metadata)
                return content.strip()
            if attempt == self._max_retries:
                raise AIServiceError(error) from None
            time.sleep(0.5 * (2 ** attempt))
        raise AIServiceError("The AI request could not be completed.")

    def _response_metadata(self, response: object, max_tokens: int) -> dict[str, object]:
        choices = getattr(response, "choices", None)
        choice = choices[0] if isinstance(choices, list) and choices else None
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        model = getattr(response, "model", None)
        if not isinstance(model, str) or self._key in model or not re.fullmatch(r"[\w:./-]{1,128}", model):
            model = None
        finish = getattr(choice, "finish_reason", None)
        if finish not in (None, "stop", "length", "tool_calls", "function_call", "content_filter"):
            finish = "unrecognized"
        reasoning_lengths = {}
        for field in ("reasoning_content", "reasoning", "thinking"):
            value = getattr(message, field, None)
            if value is not None:
                reasoning_lengths[field] = len(value) if isinstance(value, str) else None
        return {
            "stage": "api_response", "request_number": self.request_count, "max_tokens": max_tokens,
            "model": model, "choices_present": choices is not None,
            "choice_count": len(choices) if isinstance(choices, list) else 0,
            "finish_reason": finish, "content_type": type(content).__name__,
            "content_characters": len(content) if isinstance(content, str) else None,
            "reasoning_fields_present": bool(reasoning_lengths), "reasoning_field_lengths": reasoning_lengths,
            "usage": _token_usage(response), "validation_failure_category": None,
            "api_exception_type": None,
        }

    def _reject(self, metadata: dict[str, object], category: str, message: str) -> None:
        if self._diagnostics:
            self._diagnostics({**metadata, "validation_failure_category": category})
        raise AIServiceError(message, category=category)

    def _report_exception(self, exception: str, category: str, max_tokens: int, status: int | None = None) -> None:
        if self._diagnostics:
            self._diagnostics({
                "stage": "api_response", "request_number": self.request_count, "max_tokens": max_tokens,
                "api_exception_type": exception, "http_status": status, "validation_failure_category": category,
            })

    def close(self) -> None:
        """Release the SDK's HTTP connections when the application is finished."""
        self._client.close()
