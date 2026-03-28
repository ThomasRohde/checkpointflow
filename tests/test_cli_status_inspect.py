from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from checkpointflow.cli import app

runner = CliRunner()


def _run_completed_workflow(tmp_path: Path) -> str:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: greet
      kind: cli
      command: echo hello
    - id: done
      kind: end
""")
    store = str(tmp_path / "store")
    result = runner.invoke(
        app, ["run", "-f", str(wf), "--input", "{}"], env={"CHECKPOINTFLOW_BASE_DIR": store}
    )
    return json.loads(result.stdout)["run_id"]


def test_status_help_shows_options() -> None:
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0
    assert "--run-id" in result.stdout


def test_status_returns_json_envelope(tmp_path: Path) -> None:
    run_id = _run_completed_workflow(tmp_path)
    result = runner.invoke(
        app,
        ["status", "--run-id", run_id],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code == 0
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["status"] == "completed"
    assert envelope["command"] == "status"


def test_status_run_not_found(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["status", "--run-id", "fake"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code != 0
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False


def test_inspect_help_shows_options() -> None:
    result = runner.invoke(app, ["inspect", "--help"])
    assert result.exit_code == 0
    assert "--run-id" in result.stdout


def test_inspect_returns_step_results(tmp_path: Path) -> None:
    run_id = _run_completed_workflow(tmp_path)
    result = runner.invoke(
        app,
        ["inspect", "--run-id", run_id],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code == 0
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert len(envelope["result"]["step_results"]) == 2


def test_inspect_run_not_found(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["inspect", "--run-id", "fake"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code != 0
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False
