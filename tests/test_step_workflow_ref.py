from __future__ import annotations

from pathlib import Path
from typing import Any

from checkpointflow.engine.steps.workflow_ref_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import WorkflowRefStep

SUB_WORKFLOW = """\
schema_version: checkpointflow/v1
workflow:
  id: sub_workflow
  defaults:
    shell: bash
  inputs:
    type: object
    properties:
      greeting:
        type: string
  steps:
    - id: greet
      kind: cli
      command: "printf '{\\\"message\\\": \\\"hello ${inputs.greeting}\\\"}'"
      outputs:
        type: object
        properties:
          message:
            type: string
    - id: done
      kind: end
      result:
        message: ${steps.greet.outputs.message}
"""

SUB_WORKFLOW_NO_END = """\
schema_version: checkpointflow/v1
workflow:
  id: sub_no_end
  defaults:
    shell: bash
  inputs:
    type: object
  steps:
    - id: step1
      kind: cli
      command: "printf '{\\\"val\\\": 42}'"
      outputs:
        type: object
        properties:
          val:
            type: integer
"""


def _ctx(tmp_path: Path, **kwargs: Any) -> RunContext:
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    (run_dir / "stdout").mkdir(exist_ok=True)
    (run_dir / "stderr").mkdir(exist_ok=True)
    return RunContext(
        run_id="test",
        inputs=kwargs.get("inputs", {}),
        step_outputs=kwargs.get("step_outputs", {}),
        run_dir=run_dir,
    )


def test_workflow_ref_runs_subworkflow(tmp_path: Path) -> None:
    sub_path = tmp_path / "sub.yaml"
    sub_path.write_text(SUB_WORKFLOW)
    step = WorkflowRefStep.model_validate(
        {
            "id": "sub",
            "kind": "workflow",
            "workflow_ref": str(sub_path),
            "inputs": {"greeting": "world"},
        }
    )
    result = execute(step, _ctx(tmp_path))
    assert result.success is True
    assert result.outputs is not None
    assert result.outputs["message"] == "hello world"


def test_workflow_ref_file_not_found(tmp_path: Path) -> None:
    step = WorkflowRefStep.model_validate(
        {
            "id": "sub",
            "kind": "workflow",
            "workflow_ref": str(tmp_path / "missing.yaml"),
        }
    )
    result = execute(step, _ctx(tmp_path))
    assert result.success is False
    assert "not found" in (result.error_message or "").lower()


def test_workflow_ref_no_end_step(tmp_path: Path) -> None:
    sub_path = tmp_path / "sub.yaml"
    sub_path.write_text(SUB_WORKFLOW_NO_END)
    step = WorkflowRefStep.model_validate(
        {
            "id": "sub",
            "kind": "workflow",
            "workflow_ref": str(sub_path),
        }
    )
    result = execute(step, _ctx(tmp_path))
    assert result.success is True


def test_workflow_ref_with_interpolated_inputs(tmp_path: Path) -> None:
    sub_path = tmp_path / "sub.yaml"
    sub_path.write_text(SUB_WORKFLOW)
    step = WorkflowRefStep.model_validate(
        {
            "id": "sub",
            "kind": "workflow",
            "workflow_ref": str(sub_path),
            "inputs": {"greeting": "${inputs.name}"},
        }
    )
    result = execute(step, _ctx(tmp_path, inputs={"name": "claude"}))
    assert result.success is True
    assert result.outputs is not None
    assert result.outputs["message"] == "hello claude"
