from pathlib import Path

import pytest

from bank_simulator.config import DEFAULT_AI_API_URL, load_settings
from bank_simulator.services.content_service import ContentService


@pytest.fixture(autouse=True)
def clean_ai_environment(monkeypatch):
    for variable in ("AI_API_URL", "AI_API_KEY", "AI_MODEL"):
        monkeypatch.delenv(variable, raising=False)


def test_valid_dotenv_with_environment_overrides(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AI_API_URL=https://example.com/v1\nAI_API_KEY=test-key-from-file\nAI_MODEL=test-model-from-file\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_MODEL", "test-model-from-environment")

    settings = load_settings(env_file)
    assert settings.require_ai_configuration() is settings
    assert settings.ai_api_url == "https://example.com/v1"
    assert settings.ai_model == "test-model-from-environment"
    assert settings.ai_api_key.get_secret_value() == "test-key-from-file"
    assert "test-key-from-file" not in repr(settings)
    assert "test-key-from-file" not in settings.model_dump_json()


def test_missing_key_does_not_break_phase_one(tmp_path):
    settings = load_settings(tmp_path / ".env")
    assert settings.ai_api_url == DEFAULT_AI_API_URL
    assert ContentService().get_client("maryam").name
    with pytest.raises(ValueError, match="Set AI_API_KEY"):
        settings.require_ai_configuration()


def test_example_has_selected_cloud_model_and_placeholder_key():
    settings = load_settings(Path(__file__).resolve().parents[1] / ".env.example")
    assert settings.ai_api_url == "https://ollama.com/v1"
    assert settings.ai_model == "deepseek-v4.1-flash"
    assert settings.ai_api_key.get_secret_value() == "your_ollama_cloud_api_key"
    with pytest.raises(ValueError, match="Set AI_API_KEY"):
        settings.require_ai_configuration()


def test_server_environment_works_without_dotenv(monkeypatch):
    monkeypatch.setenv("AI_API_URL", "https://ollama.com/v1")
    monkeypatch.setenv("AI_API_KEY", "synthetic-server-key")
    monkeypatch.setenv("AI_MODEL", "deepseek-v4.1-flash")

    settings = load_settings(None)
    assert settings.require_ai_configuration() is settings
    assert settings.ai_api_url == "https://ollama.com/v1"
    assert settings.ai_model == "deepseek-v4.1-flash"
    assert bool(settings.ai_api_key.get_secret_value())
    assert "synthetic-server-key" not in repr(settings)
    assert "synthetic-server-key" not in settings.model_dump_json()


@pytest.mark.parametrize(
    ("variable", "field", "value"),
    [
        ("AI_API_URL", "ai_api_url", "https://environment.example/v1"),
        ("AI_API_KEY", "ai_api_key", "synthetic-environment-key"),
        ("AI_MODEL", "ai_model", "deepseek-v4.1-flash"),
    ],
)
def test_each_environment_value_overrides_dotenv(monkeypatch, tmp_path, variable, field, value):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AI_API_URL=https://file.example/v1\nAI_API_KEY=synthetic-file-key\nAI_MODEL=file-model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(variable, value)

    settings = load_settings(env_file)
    loaded_value = getattr(settings, field)
    if field == "ai_api_key":
        loaded_value = loaded_value.get_secret_value()
    assert loaded_value == value


def test_empty_environment_key_overrides_dotenv_and_requires_configuration(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AI_API_KEY=synthetic-file-key\nAI_MODEL=deepseek-v4.1-flash\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_API_KEY", "")

    settings = load_settings(env_file)
    assert not settings.ai_api_key.get_secret_value()
    with pytest.raises(ValueError, match="Set AI_API_KEY") as error:
        settings.require_ai_configuration()
    assert "synthetic-file-key" not in str(error.value)


def test_example_placeholders_require_replacement(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "your_ollama_cloud_api_key")
    monkeypatch.setenv("AI_MODEL", "your_selected_cloud_model")
    with pytest.raises(ValueError, match="Set AI_API_KEY"):
        load_settings(None).require_ai_configuration()

    monkeypatch.setenv("AI_API_KEY", "test-key")
    with pytest.raises(ValueError, match="Set AI_MODEL"):
        load_settings(None).require_ai_configuration()


@pytest.mark.parametrize("url", ["not-a-url/test-key", "https://user:test-key@example.com/v1"])
def test_invalid_ai_configuration_does_not_expose_secrets(monkeypatch, url):
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_API_URL", url)
    settings = load_settings(None)

    with pytest.raises(ValueError, match="AI_API_URL") as error:
        settings.require_ai_configuration()
    assert "test-key" not in str(error.value)
    assert "test-key" not in repr(settings)
