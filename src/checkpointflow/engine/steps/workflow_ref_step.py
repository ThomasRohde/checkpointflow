from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from checkpointflow.engine.evaluator import EvaluatorError, interpolate_values
from checkpointflow.models.errors import ErrorCode
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import (
    AwaitEventStep,
    EndStep,
    SwitchStep,
    WorkflowDocument,
    WorkflowRefStep,
)


def execute(step: WorkflowRefStep, ctx: RunContext) -> StepResult:
    """Execute a referenced sub-workflow and return its result."""
    # Resolve workflow path
    workflow_path = Path(step.workflow_ref)
    if not workflow_path.exists():
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_FILE_NOT_FOUND,
            error_message=f"Step '{step.id}' workflow file not found: {workflow_path}",
        )

    # Load and parse sub-workflow
    try:
        raw_text = workflow_path.read_text(encoding="utf-8")
        doc_dict = yaml.safe_load(raw_text)
        doc = WorkflowDocument.model_validate(doc_dict)
    except Exception as exc:
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=f"Step '{step.id}' failed to load workflow: {exc}",
        )

    sub_workflow = doc.workflow

    # Build sub-workflow inputs from the step's inputs field
    eval_ctx = ctx.build_eval_context()
    sub_inputs: dict[str, Any] = {}
    if step.inputs:
        try:
            sub_inputs = interpolate_values(step.inputs, eval_ctx)
        except EvaluatorError as exc:
            return StepResult(
                success=False,
                error_code=ErrorCode.ERR_STEP_FAILED,
                error_message=f"Step '{step.id}' input interpolation failed: {exc}",
            )

    # Execute sub-workflow steps with support for SwitchStep jumps
    all_sub_steps = list(sub_workflow.steps)
    sub_step_outputs: dict[str, dict[str, Any]] = {}
    final_result: dict[str, Any] | None = None

    idx = 0
    while idx < len(all_sub_steps):
        sub_step = all_sub_steps[idx]

        if isinstance(sub_step, AwaitEventStep):
            return StepResult(
                success=False,
                error_code=ErrorCode.ERR_STEP_FAILED,
                error_message=(
                    f"Step '{step.id}' sub-workflow step '{sub_step.id}': "
                    f"await_event is not supported in sub-workflow execution."
                ),
            )

        sub_ctx = RunContext(
            run_id=ctx.run_id,
            inputs=sub_inputs,
            step_outputs=sub_step_outputs,
            run_dir=ctx.run_dir,
            defaults=sub_workflow.defaults or {},
        )

        from checkpointflow.engine.steps.dispatch import dispatch_step

        result = dispatch_step(sub_step, sub_ctx, workflow_steps=all_sub_steps)

        if not result.success:
            return StepResult(
                success=False,
                error_code=result.error_code,
                error_message=(
                    f"Step '{step.id}' sub-workflow step '{sub_step.id}' failed: "
                    f"{result.error_message}"
                ),
            )

        if result.outputs is not None:
            sub_step_outputs[sub_step.id] = result.outputs

        if isinstance(sub_step, EndStep):
            final_result = result.outputs
            break

        # SwitchStep: jump to target
        if isinstance(sub_step, SwitchStep) and result.outputs:
            next_step_id = result.outputs.get("_next_step_id")
            if next_step_id:
                step_ids = [s.id for s in all_sub_steps]
                if next_step_id in step_ids:
                    idx = step_ids.index(next_step_id)
                    continue

        idx += 1

    return StepResult(success=True, outputs=final_result or sub_step_outputs)
