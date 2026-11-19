"""Read optional provider settings without initiating an API connection."""

import os
from pathlib import Path
from typing import Self

from dotenv import dotenv_values
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, TypeAdapter, ValidationError

from .data_loader import PROJECT_ROOT


DEFAULT_AI_API_URL = "https://ollama.com/v1"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
_HTTP_URL = TypeAdapter(AnyHttpUrl)


class Settings(BaseModel):
    """Environment settings that may be incomplete during Phase 1."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    ai_api_url: str = Field(default=DEFAULT_AI_API_URL, repr=False)
    ai_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    ai_model: str = ""

    def require_ai_configuration(self) -> Self:
        """Validate settings when constructing a provider integration."""
        try:
            url = _HTTP_URL.validate_python(self.ai_api_url)
        except ValidationError:
            raise ValueError("AI_API_URL must be an absolute HTTP(S) URL.") from None
        if url.username is not None or url.password is not None:
            raise ValueError("AI_API_URL must not contain credentials.")
        if self.ai_api_key.get_secret_value().strip() in {"", "your_ollama_cloud_api_key"}:
            raise ValueError("Set AI_API_KEY before initializing AI integration.")
        if self.ai_model.strip() in {"", "your_selected_cloud_model"}:
            raise ValueError("Set AI_MODEL before initializing AI integration.")
        return self


def load_settings(env_file: Path | None = DEFAULT_ENV_FILE) -> Settings:
    """Load `.env` defaults with process environment variables taking precedence."""
    file_values = dotenv_values(env_file, interpolate=False) if env_file is not None else {}

    def read(key: str, default: str = "") -> str:
        return os.environ.get(key, file_values.get(key) or default).strip()

    return Settings(
        ai_api_url=read("AI_API_URL", DEFAULT_AI_API_URL),
        ai_api_key=SecretStr(read("AI_API_KEY")),
        ai_model=read("AI_MODEL"),
    )
