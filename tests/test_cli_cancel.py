from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from checkpointflow.cli import app
from checkpointflow.engine.runner import resume_workflow

runner = CliRunner()


def _run_to_waiting(tmp_path: Path) -> str:
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
      event_name: ev
      input_schema:
        type: object
    - id: done
      kind: end
""")
    store = str(tmp_path / "store")
    result = runner.invoke(
        app, ["run", "-f", str(wf), "--input", "{}"], env={"CHECKPOINTFLOW_BASE_DIR": store}
    )
    return json.loads(result.stdout)["run_id"]


def _run_completed(tmp_path: Path) -> str:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: done
      kind: end
""")
    store = str(tmp_path / "store")
    result = runner.invoke(
        app, ["run", "-f", str(wf), "--input", "{}"], env={"CHECKPOINTFLOW_BASE_DIR": store}
    )
    return json.loads(result.stdout)["run_id"]


def test_cancel_help_shows_options() -> None:
    result = runner.invoke(app, ["cancel", "--help"])
    assert result.exit_code == 0
    assert "--run-id" in result.stdout
    assert "--reason" in result.stdout


def test_cancel_waiting_run(tmp_path: Path) -> None:
    run_id = _run_to_waiting(tmp_path)
    result = runner.invoke(
        app,
        ["cancel", "--run-id", run_id, "--reason", "no longer needed"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code == 0
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["status"] == "cancelled"


def test_cancel_completed_run_fails(tmp_path: Path) -> None:
    run_id = _run_completed(tmp_path)
    result = runner.invoke(
        app,
        ["cancel", "--run-id", run_id, "--reason", "too late"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False


def test_cancel_nonexistent_run(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["cancel", "--run-id", "fake", "--reason", "gone"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "ERR_RUN_NOT_FOUND"


def test_cancelled_run_cannot_be_resumed(tmp_path: Path) -> None:
    run_id = _run_to_waiting(tmp_path)
    runner.invoke(
        app,
        ["cancel", "--run-id", run_id, "--reason", "changed mind"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    env = resume_workflow(run_id, "ev", "{}", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == "ERR_RUN_NOT_WAITING"
