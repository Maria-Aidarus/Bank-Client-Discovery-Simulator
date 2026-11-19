"""Small OpenAI SDK adapter for Ollama Cloud with bounded, sanitized failures."""

import time
from collections.abc import Sequence
from typing import Protocol

from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError, OpenAI
from openai.types.chat import ChatCompletionMessageParam

from ..config import Settings, load_settings


class AIServiceError(RuntimeError):
    """An AI request failed. Messages are safe to display to the user."""


class ChatAdapter(Protocol):
    def complete(
        self, messages: Sequence[ChatCompletionMessageParam], *, max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> str:
        """Return a nonempty assistant response or raise AIServiceError."""
        ...


class OllamaCloudAdapter:
    """Share one SDK client across both agents within an application lifecycle."""

    def __init__(
        self, settings: Settings | None = None, *, client: OpenAI | None = None,
        timeout: float = 60.0, max_retries: int = 1,
    ) -> None:
        settings = (settings or load_settings()).require_ai_configuration()
        if not 0 <= max_retries <= 2:
            raise ValueError("max_retries must be between zero and two.")
        if not 0 < timeout <= 120:
            raise ValueError("timeout must be greater than zero and at most 120 seconds.")
        self.model = settings.ai_model
        self.request_count = 0
        self.response_models: set[str] = set()
        self._key = settings.ai_api_key.get_secret_value()
        self._max_retries = max_retries
        # Disable SDK retries so each counted attempt has exactly one HTTP request.
        self._client = client.with_options(timeout=timeout, max_retries=0) if client else OpenAI(
            base_url=settings.ai_api_url, api_key=self._key, timeout=timeout, max_retries=0,
        )

    def complete(
        self, messages: Sequence[ChatCompletionMessageParam], *, max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> str:
        for attempt in range(self._max_retries + 1):
            self.request_count += 1
            try:
                response = self._client.chat.completions.create(
                    model=self.model, messages=list(messages), max_tokens=max_tokens,
                    temperature=temperature,
                )
            except APITimeoutError:
                error = "The AI request timed out. Please try again."
            except APIConnectionError:
                error = "Could not connect to Ollama Cloud. Please try again."
            except APIStatusError as exc:
                if exc.status_code in (401, 403):
                    raise AIServiceError("Ollama Cloud authentication failed. Check AI_API_KEY and access.") from None
                if exc.status_code == 404:
                    raise AIServiceError("The configured model or API endpoint is unavailable.") from None
                if exc.status_code not in (408, 409, 429) and exc.status_code < 500:
                    raise AIServiceError("Ollama Cloud rejected the AI request. Check configuration.") from None
                error = "Ollama Cloud is temporarily unavailable. Please try again."
                if exc.status_code == 429:
                    error = "Ollama Cloud rate limit reached. Please try again later."
            except APIError:
                raise AIServiceError("Ollama Cloud returned an invalid API response.") from None
            else:
                choices = getattr(response, "choices", None)
                if not isinstance(choices, list) or not choices:
                    raise AIServiceError("Ollama Cloud returned no response choices.")
                choice = choices[0]
                if getattr(choice, "finish_reason", None) != "stop":
                    raise AIServiceError("Ollama Cloud returned an incomplete or unsupported response.")
                content = getattr(getattr(choice, "message", None), "content", None)
                if not isinstance(content, str) or not content.strip():
                    raise AIServiceError("Ollama Cloud returned an empty response.")
                if self._key in content:
                    raise AIServiceError("The AI response contained sensitive configuration and was rejected.")
                reported_model = getattr(response, "model", None)
                if isinstance(reported_model, str) and self._key not in reported_model:
                    self.response_models.add(reported_model)
                return content.strip()
            if attempt == self._max_retries:
                raise AIServiceError(error) from None
            time.sleep(0.5 * (2 ** attempt))
        raise AIServiceError("The AI request could not be completed.")

    def close(self) -> None:
        """Release the SDK's HTTP connections when the application is finished."""
        self._client.close()
