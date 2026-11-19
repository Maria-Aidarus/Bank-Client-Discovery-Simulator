"""Verify live API use requires an explicit command-line opt-in."""

import runpy
from pathlib import Path

import pytest


def test_smoke_script_requires_live_flag(monkeypatch, capsys):
    script = Path(__file__).resolve().parents[1] / "scripts" / "smoke_test_ai.py"
    monkeypatch.setattr("sys.argv", [str(script)])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(script), run_name="__main__")
    assert error.value.code == 2
    assert "Pass --live" in capsys.readouterr().err
