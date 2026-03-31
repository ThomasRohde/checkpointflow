from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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


def test_workflow_ref_runs_subworkflow(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
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
    result = execute(step, run_ctx())
    assert result.success is True
    assert result.outputs is not None
    assert result.outputs["message"] == "hello world"


def test_workflow_ref_file_not_found(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    step = WorkflowRefStep.model_validate(
        {
            "id": "sub",
            "kind": "workflow",
            "workflow_ref": str(tmp_path / "missing.yaml"),
        }
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert "not found" in (result.error_message or "").lower()


def test_workflow_ref_no_end_step(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    sub_path = tmp_path / "sub.yaml"
    sub_path.write_text(SUB_WORKFLOW_NO_END)
    step = WorkflowRefStep.model_validate(
        {
            "id": "sub",
            "kind": "workflow",
            "workflow_ref": str(sub_path),
        }
    )
    result = execute(step, run_ctx())
    assert result.success is True


def test_workflow_ref_with_interpolated_inputs(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
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
    result = execute(step, run_ctx(inputs={"name": "claude"}))
    assert result.success is True
    assert result.outputs is not None
    assert result.outputs["message"] == "hello claude"


SUB_WORKFLOW_API = """\
schema_version: checkpointflow/v1
workflow:
  id: sub_api
  inputs:
    type: object
  steps:
    - id: call_api
      kind: api
      method: GET
      url: "http://127.0.0.1:1/unreachable"
"""

SUB_WORKFLOW_SWITCH = """\
schema_version: checkpointflow/v1
workflow:
  id: sub_switch
  defaults:
    shell: bash
  inputs:
    type: object
    properties:
      mode:
        type: string
  steps:
    - id: route
      kind: switch
      cases:
        - when: 'inputs.mode == "fast"'
          next: end_fast
        - when: 'inputs.mode == "slow"'
          next: end_slow
      default: end_slow
    - id: end_fast
      kind: end
      result:
        chosen: fast
    - id: end_slow
      kind: end
      result:
        chosen: slow
"""

SUB_WORKFLOW_AWAIT = """\
schema_version: checkpointflow/v1
workflow:
  id: sub_await
  inputs:
    type: object
  steps:
    - id: wait_for_event
      kind: await_event
      audience: user
      event_name: approval
      input_schema:
        type: object
"""

SUB_WORKFLOW_FOREACH = """\
schema_version: checkpointflow/v1
workflow:
  id: sub_foreach
  defaults:
    shell: bash
  inputs:
    type: object
    properties:
      items:
        type: array
  steps:
    - id: loop
      kind: foreach
      items: "${inputs.items}"
      body:
        - id: echo_item
          kind: cli
          command: "printf '{\\\"val\\\": \\\"${item}\\\"}'"
          outputs:
            type: object
            properties:
              val:
                type: string
"""


def test_workflow_ref_with_api_step_in_subworkflow(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
    sub_path = tmp_path / "sub_api.yaml"
    sub_path.write_text(SUB_WORKFLOW_API)
    step = WorkflowRefStep.model_validate(
        {
            "id": "sub",
            "kind": "workflow",
            "workflow_ref": str(sub_path),
        }
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert result.error_message is not None
    assert "call_api" in result.error_message


def test_workflow_ref_with_switch_in_subworkflow(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
    sub_path = tmp_path / "sub_switch.yaml"
    sub_path.write_text(SUB_WORKFLOW_SWITCH)

    step_fast = WorkflowRefStep.model_validate(
        {
            "id": "sub",
            "kind": "workflow",
            "workflow_ref": str(sub_path),
            "inputs": {"mode": "fast"},
        }
    )
    result_fast = execute(step_fast, run_ctx())
    assert result_fast.success is True
    assert result_fast.outputs is not None
    assert result_fast.outputs["chosen"] == "fast"

    step_slow = WorkflowRefStep.model_validate(
        {
            "id": "sub",
            "kind": "workflow",
            "workflow_ref": str(sub_path),
            "inputs": {"mode": "slow"},
        }
    )
    result_slow = execute(step_slow, run_ctx())
    assert result_slow.success is True
    assert result_slow.outputs is not None
    assert result_slow.outputs["chosen"] == "slow"


def test_workflow_ref_with_await_event_returns_error(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
    sub_path = tmp_path / "sub_await.yaml"
    sub_path.write_text(SUB_WORKFLOW_AWAIT)
    step = WorkflowRefStep.model_validate(
        {
            "id": "sub",
            "kind": "workflow",
            "workflow_ref": str(sub_path),
        }
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert result.error_message is not None
    assert "await_event" in result.error_message
    assert "not supported" in result.error_message


def test_workflow_ref_with_foreach_in_subworkflow(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
    sub_path = tmp_path / "sub_foreach.yaml"
    sub_path.write_text(SUB_WORKFLOW_FOREACH)
    step = WorkflowRefStep.model_validate(
        {
            "id": "sub",
            "kind": "workflow",
            "workflow_ref": str(sub_path),
            "inputs": {"items": ["alpha", "beta", "gamma"]},
        }
    )
    result = execute(step, run_ctx())
    assert result.success is True
    assert result.outputs is not None
    loop_outputs = result.outputs.get("loop")
    assert loop_outputs is not None
    iterations = loop_outputs["iterations"]
    assert len(iterations) == 3
