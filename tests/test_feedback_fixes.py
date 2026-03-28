"""Tests for cpf-feedback-report fixes: shell, type-preserving interpolation, inspect paths."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from checkpointflow.engine.queries import query_inspect
from checkpointflow.engine.runner import run_workflow
from checkpointflow.engine.steps.end_step import execute as end_execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import EndStep

# --- Fix 1: Shell selection ---


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell test requires Windows")
def test_cli_step_powershell_shell(tmp_path: Path) -> None:
    """shell: powershell should run PowerShell commands."""
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: ps
      kind: cli
      shell: powershell
      command: Write-Output "hello-from-powershell"
    - id: done
      kind: end
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.status == "completed"


# --- Fix 2: Type-preserving interpolation ---


def test_end_step_preserves_int_type(tmp_path: Path) -> None:
    """Pure ${...} reference should preserve numeric type, not stringify."""
    step = EndStep.model_validate(
        {
            "id": "done",
            "kind": "end",
            "result": {"count": "${steps.emit.outputs.count}"},
        }
    )
    ctx = RunContext(
        run_id="test",
        inputs={},
        step_outputs={"emit": {"count": 42}},
        run_dir=tmp_path,
    )
    result = end_execute(step, ctx)
    assert result.outputs is not None
    assert result.outputs["count"] == 42
    assert isinstance(result.outputs["count"], int)


def test_end_step_preserves_bool_type(tmp_path: Path) -> None:
    step = EndStep.model_validate(
        {
            "id": "done",
            "kind": "end",
            "result": {"flag": "${steps.check.outputs.passed}"},
        }
    )
    ctx = RunContext(
        run_id="test",
        inputs={},
        step_outputs={"check": {"passed": True}},
        run_dir=tmp_path,
    )
    result = end_execute(step, ctx)
    assert result.outputs["flag"] is True


def test_end_step_mixed_string_stays_string(tmp_path: Path) -> None:
    """When ${...} is part of a larger string, result is still a string."""
    step = EndStep.model_validate(
        {
            "id": "done",
            "kind": "end",
            "result": {"greeting": "Hello, ${inputs.name}!"},
        }
    )
    ctx = RunContext(
        run_id="test",
        inputs={"name": "Alice"},
        step_outputs={},
        run_dir=tmp_path,
    )
    result = end_execute(step, ctx)
    assert result.outputs["greeting"] == "Hello, Alice!"
    assert isinstance(result.outputs["greeting"], str)


def test_type_preservation_in_full_workflow(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: emit
      kind: cli
      command: python -c "import json; print(json.dumps({'count':5,'active':True}))"
      outputs:
        type: object
        properties:
          count: { type: integer }
          active: { type: boolean }
    - id: done
      kind: end
      result:
        total: ${steps.emit.outputs.count}
        is_active: ${steps.emit.outputs.active}
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.result is not None
    assert env.result["total"] == 5
    assert isinstance(env.result["total"], int)
    assert env.result["is_active"] is True


# --- Fix 3: stdout/stderr paths in inspect ---


def test_inspect_includes_artifact_paths(tmp_path: Path) -> None:
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
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None

    insp = query_inspect(env.run_id, base_dir=tmp_path / "store")
    cli_step = insp.result["step_results"][0]
    assert cli_step["step_id"] == "greet"
    assert cli_step["stdout_path"] is not None
    assert "stdout" in cli_step["stdout_path"]
    assert cli_step["stderr_path"] is not None
