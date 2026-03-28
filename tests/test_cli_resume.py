from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from checkpointflow.cli import app

runner = CliRunner()


def _write_await_workflow(tmp_path: Path) -> Path:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: wait
      kind: await_event
      audience: user
      event_name: input_needed
      input_schema:
        type: object
    - id: done
      kind: end
""")
    return wf


def _run_to_waiting(tmp_path: Path) -> tuple[str, Path]:
    wf = _write_await_workflow(tmp_path)
    store = str(tmp_path / "store")
    result = runner.invoke(
        app, ["run", "-f", str(wf), "--input", "{}"], env={"CHECKPOINTFLOW_BASE_DIR": store}
    )
    envelope = json.loads(result.stdout)
    return envelope["run_id"], tmp_path


def test_resume_help_shows_options() -> None:
    result = runner.invoke(app, ["resume", "--help"])
    assert result.exit_code == 0
    assert "run-id" in result.stdout
    assert "event" in result.stdout
    assert "input" in result.stdout


def test_resume_valid_exits_zero(tmp_path: Path) -> None:
    run_id, tp = _run_to_waiting(tmp_path)
    result = runner.invoke(
        app,
        ["resume", "--run-id", run_id, "--event", "input_needed", "--input", "{}"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tp / "store")},
    )
    assert result.exit_code == 0
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["status"] == "completed"


def test_resume_run_not_found_exits(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["resume", "--run-id", "fake", "--event", "ev", "--input", "{}"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code != 0
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False


def test_resume_wrong_event_errors(tmp_path: Path) -> None:
    run_id, tp = _run_to_waiting(tmp_path)
    result = runner.invoke(
        app,
        ["resume", "--run-id", run_id, "--event", "wrong", "--input", "{}"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tp / "store")},
    )
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "ERR_RESUME_EVENT_MISMATCH"
