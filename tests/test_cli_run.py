from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from typer.testing import CliRunner

from checkpointflow.cli import app

runner = CliRunner()


def test_run_help_exits_zero() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0


def test_run_valid_workflow_exits_zero(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    result = runner.invoke(
        app,
        ["run", "-f", str(wf), "--input", "{}"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code == 0


def test_run_returns_json_envelope(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    result = runner.invoke(
        app,
        ["run", "-f", str(wf), "--input", "{}"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["command"] == "run"
    assert envelope["status"] == "completed"


def test_run_envelope_has_run_id(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    result = runner.invoke(
        app,
        ["run", "-f", str(wf), "--input", "{}"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    envelope = json.loads(result.stdout)
    assert "run_id" in envelope
    assert len(envelope["run_id"]) > 0


def test_run_envelope_has_workflow_id(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    result = runner.invoke(
        app,
        ["run", "-f", str(wf), "--input", "{}"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    envelope = json.loads(result.stdout)
    assert envelope["workflow_id"] == "test_wf"


def test_run_nonexistent_file_exits_ten(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["run", "-f", str(tmp_path / "nope.yaml"), "--input", "{}"],
    )
    assert result.exit_code == 10


def test_run_invalid_input_exits_ten(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    result = runner.invoke(
        app,
        ["run", "-f", str(wf), "--input", "{bad"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code == 10


def test_run_step_failure_exits_thirty(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: fail
      kind: cli
      command: exit 1
    - id: done
      kind: end""",
    )
    result = runner.invoke(
        app,
        ["run", "-f", str(wf), "--input", "{}"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code == 30


def test_run_api_step_attempts_request(tmp_path: Path) -> None:
    """API steps are now supported. A connection error results in exit code 30 (step failed)."""
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: test_wf
  inputs:
    type: object
  steps:
    - id: call_api
      kind: api
      method: GET
      url: http://127.0.0.1:1/unreachable
    - id: done
      kind: end
""")
    result = runner.invoke(
        app,
        ["run", "-f", str(wf), "--input", "{}"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code == 30
