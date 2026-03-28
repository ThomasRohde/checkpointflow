from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from checkpointflow.engine.evaluator import EvaluatorError, resolve_path
from checkpointflow.engine.steps import cli_step, end_step
from checkpointflow.models.errors import ErrorCode
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import CliStep, EndStep, WorkflowDocument, WorkflowRefStep

_FULL_EXPR = re.compile(r"^\$\{([^}]+)\}$")


def _interpolate_input_values(value: Any, eval_ctx: dict[str, Any]) -> Any:
    """Recursively interpolate ${...} expressions in input values."""
    if isinstance(value, str) and "${" in value:
        m = _FULL_EXPR.match(value.strip())
        if m:
            return resolve_path(m.group(1).strip(), eval_ctx)
        from checkpointflow.engine.evaluator import interpolate

        return interpolate(value, eval_ctx)
    if isinstance(value, dict):
        return {k: _interpolate_input_values(v, eval_ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_input_values(v, eval_ctx) for v in value]
    return value


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
    eval_ctx: dict[str, Any] = {
        "inputs": ctx.inputs,
        "steps": {sid: {"outputs": outs} for sid, outs in ctx.step_outputs.items()},
    }
    sub_inputs: dict[str, Any] = {}
    if step.inputs:
        try:
            sub_inputs = _interpolate_input_values(step.inputs, eval_ctx)
        except EvaluatorError as exc:
            return StepResult(
                success=False,
                error_code=ErrorCode.ERR_STEP_FAILED,
                error_message=f"Step '{step.id}' input interpolation failed: {exc}",
            )

    # Execute sub-workflow steps linearly
    sub_step_outputs: dict[str, dict[str, Any]] = {}
    final_result: dict[str, Any] | None = None

    for sub_step in sub_workflow.steps:
        sub_ctx = RunContext(
            run_id=ctx.run_id,
            inputs=sub_inputs,
            step_outputs=sub_step_outputs,
            run_dir=ctx.run_dir,
            defaults=sub_workflow.defaults or {},
        )

        if isinstance(sub_step, CliStep):
            result = cli_step.execute(sub_step, sub_ctx)
        elif isinstance(sub_step, EndStep):
            result = end_step.execute(sub_step, sub_ctx)
        else:
            return StepResult(
                success=False,
                error_code=ErrorCode.ERR_STEP_FAILED,
                error_message=(
                    f"Step '{step.id}' sub-workflow step '{sub_step.id}' "
                    f"kind '{sub_step.kind}' not supported in sub-workflow execution."
                ),
            )

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

    return StepResult(success=True, outputs=final_result or sub_step_outputs)
