"""Verify live API use requires an explicit command-line opt-in."""

import json
import runpy
from pathlib import Path

import pytest

from bank_simulator.agents.api_adapter import AIServiceError
from bank_simulator.models import CoachFeedback, ProductRecommendation


def test_smoke_script_requires_live_flag(monkeypatch, capsys):
    script = Path(__file__).resolve().parents[1] / "scripts" / "smoke_test_ai.py"
    monkeypatch.setattr("sys.argv", [str(script)])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(script), run_name="__main__")
    assert error.value.code == 2
    assert "Pass --live" in capsys.readouterr().err


@pytest.fixture
def smoke_main():
    script = Path(__file__).resolve().parents[1] / "scripts" / "smoke_test_ai.py"
    return runpy.run_path(str(script))["main"]


def _inject_adapter(monkeypatch, main, scripted_adapter, responses):
    instances = []

    class SmokeAdapter(scripted_adapter):
        def __init__(self, *args, diagnostics=None, **kwargs):
            super().__init__(responses)
            self.model = "synthetic-test-model"
            self.response_models = set()
            self.request_count = 0
            self.token_usage = {}
            self.sink = diagnostics
            self.closed = False
            instances.append(self)

        def complete(self, messages, **options):
            self.request_count += 1
            self.response_models.add(self.model)
            if self.sink:
                self.sink({"stage": "api_response", "request_number": self.request_count})
            return super().complete(messages, **options)

        def close(self):
            self.closed = True

    monkeypatch.setitem(main.__globals__, "OllamaCloudAdapter", SmokeAdapter)
    monkeypatch.setitem(main.__globals__, "load_settings", lambda: None)
    return instances


def _feedback():
    return json.dumps({
        "what_went_well": ["You asked about the goal and acknowledged product limitations."],
        "what_was_missed": ["Contingency planning needs a follow-up question."],
        "how_to_improve": ["Ask what happens if expected receipts arrive late."],
    })


@pytest.fixture
def saved_interview(tmp_path, recommendations, completed_interview):
    session = recommendations.submit_summary(completed_interview, "A dated savings goal.")
    session = recommendations.submit_recommendations(session, [ProductRecommendation(
        product_id="goal-saver-account", justification="Separate the goal from emergency savings.",
    )])
    path = tmp_path / "saved.json"
    path.write_text(json.dumps({"session": session.model_dump(mode="json")}))
    return path


def test_coach_only_uses_saved_session_and_writes_safe_reports(
    monkeypatch, tmp_path, smoke_main, scripted_adapter, saved_interview
):
    original = saved_interview.read_bytes()
    output = tmp_path / "result.json"
    diagnostics = tmp_path / "diagnostics.json"
    instances = _inject_adapter(monkeypatch, smoke_main, scripted_adapter, [_feedback()])
    monkeypatch.setattr("sys.argv", ["smoke", "--live", "--coach-only", str(saved_interview),
                                     "--output", str(output), "--diagnostics", str(diagnostics)])
    assert smoke_main() == 0
    adapter, = instances
    assert adapter.request_count == 1
    assert adapter.closed
    report = json.loads(output.read_text())
    assert report["session"] == json.loads(original)["session"]
    assert saved_interview.read_bytes() == original
    assert CoachFeedback.model_validate(report["feedback"])
    diagnostic = json.loads(diagnostics.read_text())
    assert "session" not in diagnostic
    assert "hidden_needs" not in json.dumps(diagnostic)
    assert "system" not in json.dumps(diagnostic)


def test_coach_failure_saves_session_and_can_be_retried_without_client_calls(
    monkeypatch, tmp_path, smoke_main, scripted_adapter, saved_interview
):
    failed_output = tmp_path / "failed.json"
    instances = _inject_adapter(monkeypatch, smoke_main, scripted_adapter, [
        AIServiceError("Truncated", category="truncated"),
        AIServiceError("Truncated", category="truncated"),
    ])
    monkeypatch.setattr("sys.argv", ["smoke", "--live", "--coach-only", str(saved_interview),
                                     "--output", str(failed_output)])
    assert smoke_main() == 1
    assert instances[0].request_count == 2
    failed = json.loads(failed_output.read_text())
    assert failed["failure_category"] == "truncated"
    assert "feedback" not in failed
    assert failed["session"] == json.loads(saved_interview.read_text())["session"]

    successful_output = tmp_path / "recovered.json"
    instances = _inject_adapter(monkeypatch, smoke_main, scripted_adapter, [_feedback()])
    monkeypatch.setattr("sys.argv", ["smoke", "--live", "--coach-only", str(failed_output),
                                     "--output", str(successful_output)])
    assert smoke_main() == 0
    assert instances[0].request_count == 1
    assert json.loads(successful_output.read_text())["session"] == failed["session"]


def test_full_mode_still_covers_three_client_turns_and_validated_feedback(
    monkeypatch, tmp_path, smoke_main, scripted_adapter
):
    output = tmp_path / "full.json"
    instances = _inject_adapter(monkeypatch, smoke_main, scripted_adapter, [
        "I own a distribution business in Doha.",
        "QAR 25,000 is available, with QAR 40,000 due soon.",
        "I prefer Sharia-compliant banking.", _feedback(),
    ])
    monkeypatch.setattr("sys.argv", ["smoke", "--live", "--output", str(output)])
    assert smoke_main() == 0
    report = json.loads(output.read_text())
    assert report["api_calls"] == instances[0].request_count == 4
    assert len(report["session"]["transcript"]) == 6
    assert report["session"]["client_id"] == "maryam"
    assert all(report["behavioral_checks"].values())
    assert CoachFeedback.model_validate(report["feedback"])


def test_invalid_saved_fixture_never_constructs_api_adapter(monkeypatch, tmp_path, smoke_main):
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"session": {"status": "active", "client_id": "missing"}}')
    monkeypatch.setattr("sys.argv", ["smoke", "--live", "--coach-only", str(invalid)])
    monkeypatch.setitem(smoke_main.__globals__, "OllamaCloudAdapter", lambda **kwargs: pytest.fail("API constructed"))
    assert smoke_main() == 1


def test_report_paths_cannot_overwrite_saved_input(monkeypatch, smoke_main, saved_interview):
    original = saved_interview.read_bytes()
    monkeypatch.setattr("sys.argv", ["smoke", "--live", "--coach-only", str(saved_interview),
                                     "--diagnostics", str(saved_interview)])
    with pytest.raises(SystemExit) as error:
        smoke_main()
    assert error.value.code == 2
    assert saved_interview.read_bytes() == original
