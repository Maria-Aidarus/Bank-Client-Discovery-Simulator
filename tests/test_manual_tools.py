import json
import runpy
from pathlib import Path

import pytest

from bank_simulator.agents.api_adapter import AIServiceError
from bank_simulator.models import CoachFeedback, InterviewSession


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FEEDBACK = json.dumps({
    "what_went_well": ["You asked about the client's situation."],
    "what_was_missed": ["Follow up on the timing of obligations."],
    "how_to_improve": ["Ask which payments have fixed dates."],
})


def _tool(name):
    return runpy.run_path(str(SCRIPTS / name))


def _adapter(monkeypatch, main, scripted_adapter, responses):
    instances = []

    class ToolAdapter(scripted_adapter):
        def __init__(self, *args, diagnostics=None, **kwargs):
            super().__init__(responses)
            self.model = "synthetic-model"
            self.response_models = {self.model}
            self.request_count = 0
            self.token_usage = {}
            self.closed = False
            instances.append(self)

        def complete(self, messages, **kwargs):
            self.request_count += 1
            return super().complete(messages, **kwargs)

        def close(self):
            self.closed = True

    monkeypatch.setitem(main.__globals__, "OllamaCloudAdapter", ToolAdapter)
    return instances


def _inputs(monkeypatch, values):
    answers = iter(values)

    def read(prompt):
        value = next(answers)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr("builtins.input", read)


@pytest.mark.parametrize("script, arguments", [
    ("manual_interview.py", []), ("evaluate_conversations.py", ["--scenario", "maryam-weak"]),
])
def test_terminal_tools_require_explicit_live_opt_in(monkeypatch, script, arguments):
    main = _tool(script)["main"]
    monkeypatch.setattr("sys.argv", [script, *arguments])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_manual_interview_retries_question_and_validates_products(
    monkeypatch, tmp_path, scripted_adapter, capsys
):
    main = _tool("manual_interview.py")["main"]
    instances = _adapter(monkeypatch, main, scripted_adapter, [
        AIServiceError("Connection failed"), "Late receipts make supplier payments difficult.", FEEDBACK,
    ])
    output = tmp_path / "manual.json"
    monkeypatch.setattr("sys.argv", ["manual", "--live", "--client", "maryam", "--output", str(output)])
    _inputs(monkeypatch, ["How do late payments affect your business?", "/retry", "/end",
                         "A timing problem needs follow-up.", "unknown-product", "business-cash-management",
                         "Useful visibility; does not fund the gap."])
    assert main() == 0
    report = json.loads(output.read_text())
    session = InterviewSession.model_validate(report["session"])
    assert len(session.transcript) == 2
    assert session.client_id == "maryam"
    assert session.selected_recommendations[0].product_id == "business-cash-management"
    assert CoachFeedback.model_validate(report["feedback"])
    assert report["student_submission_source"] == "manual"
    assert instances[0].request_count == 3 and instances[0].closed
    displayed = capsys.readouterr().out
    assert "Unknown product ID" in displayed
    assert "What went well" in displayed and "How to improve" in displayed
    assert "QAR 25,000" not in displayed
    assert "hidden_needs" not in displayed


def test_manual_coach_failure_can_be_retried_without_losing_interview(monkeypatch, tmp_path, scripted_adapter):
    main = _tool("manual_interview.py")["main"]
    instances = _adapter(monkeypatch, main, scripted_adapter, [
        "I am saving for certification.", AIServiceError("Authentication failed"), FEEDBACK,
    ])
    output = tmp_path / "retried.json"
    monkeypatch.setattr("sys.argv", ["manual", "--live", "--client", "mohamed", "--output", str(output)])
    _inputs(monkeypatch, ["What are you saving for?", "/end", "A certification goal.",
                         "goal-saver-account", "Separate goal savings.", "/retry"])
    assert main() == 0
    report = json.loads(output.read_text())
    assert len(report["session"]["transcript"]) == 2
    assert instances[0].request_count == 3
    assert report["status"] == "completed"


def test_interrupted_terminal_session_exports_completed_turns(monkeypatch, tmp_path, scripted_adapter):
    main = _tool("manual_interview.py")["main"]
    _adapter(monkeypatch, main, scripted_adapter, ["I run a distribution business."])
    output = tmp_path / "interrupted.json"
    monkeypatch.setattr("sys.argv", ["manual", "--live", "--client", "maryam", "--output", str(output)])
    _inputs(monkeypatch, ["Tell me about your business.", EOFError()])
    assert main() == 1
    report = json.loads(output.read_text())
    assert len(report["session"]["transcript"]) == 2
    assert report["feedback"] is None
    assert report["status"] == "interrupted"


def test_evaluation_scenarios_cover_both_clients_and_all_five_cases(content):
    module = _tool("evaluate_conversations.py")
    scenarios = [module["EvaluationScenario"].model_validate(record)
                 for record in json.loads(module["SCENARIO_FILE"].read_text())]
    assert {scenario.id for scenario in scenarios} == {
        f"{client.id}-{case}" for client in content.list_clients()
        for case in ("strong", "weak", "unsuitable", "natural", "product")
    }
    for scenario in scenarios:
        content.get_client(scenario.client_id)
        for choice in scenario.recommendations:
            content.get_product(choice.product_id)


def test_evaluation_runs_only_selected_case_and_leaves_rubric_for_human_review(
    monkeypatch, tmp_path, scripted_adapter
):
    main = _tool("evaluate_conversations.py")["main"]
    instances = _adapter(monkeypatch, main, scripted_adapter, [
        "I run a business.", "I want to review banking services.", FEEDBACK,
    ])
    output = tmp_path / "evaluation.json"
    monkeypatch.setattr("sys.argv", ["evaluate", "--live", "--scenario", "maryam-weak", "--output", str(output)])
    assert main() == 0
    report = json.loads(output.read_text())
    assert report["scenario_id"] == "maryam-weak"
    assert report["api_calls"] == instances[0].request_count == 3
    assert set(report["manual_review"]["scale"]) == {"1", "2", "3", "4", "5"}
    assert all(score is None for score in report["manual_review"]["scores"].values())
    assert report["session"]["selected_recommendations"][0]["product_id"] == "business-cash-management"


def test_evaluation_api_failure_preserves_history_and_does_not_fabricate_feedback(
    monkeypatch, tmp_path, scripted_adapter
):
    main = _tool("evaluate_conversations.py")["main"]
    _adapter(monkeypatch, main, scripted_adapter, ["I run a business.", AIServiceError("Connection failed")])
    output = tmp_path / "failed.json"
    monkeypatch.setattr("sys.argv", ["evaluate", "--live", "--scenario", "maryam-weak", "--output", str(output)])
    assert main() == 1
    report = json.loads(output.read_text())
    assert report["status"] == "failed"
    assert len(report["session"]["transcript"]) == 2
    assert "feedback" not in report
