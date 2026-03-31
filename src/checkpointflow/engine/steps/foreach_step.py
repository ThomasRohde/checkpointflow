from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from checkpointflow.engine.evaluator import EvaluatorError, resolve_path, strip_expression_wrapper
from checkpointflow.models.errors import ErrorCode
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import (
    ApiStep,
    AwaitEventStep,
    CliStep,
    EndStep,
    ForeachStep,
    ParallelStep,
    Step,
    SwitchStep,
    WorkflowRefStep,
)

_STEP_ADAPTER: TypeAdapter[Step] = TypeAdapter(Step)


def _parse_body_step(
    step_dict: dict[str, Any],
) -> (
    CliStep
    | ApiStep
    | AwaitEventStep
    | EndStep
    | ForeachStep
    | ParallelStep
    | SwitchStep
    | WorkflowRefStep
):
    """Parse a body step dict into a Step model."""
    try:
        return _STEP_ADAPTER.validate_python(step_dict)
    except Exception as exc:
        msg = f"Unsupported or invalid body step: {exc}"
        raise ValueError(msg) from exc


def execute(step: ForeachStep, ctx: RunContext) -> StepResult:
    """Iterate over items and execute body steps for each."""
    from checkpointflow.engine.steps.dispatch import dispatch_step

    eval_ctx = ctx.build_eval_context()

    # Resolve items expression
    items_expr = strip_expression_wrapper(step.items.strip())

    try:
        items = resolve_path(items_expr, eval_ctx)
    except EvaluatorError as exc:
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=f"Step '{step.id}' items expression failed: {exc}",
        )

    if not isinstance(items, list):
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=f"Step '{step.id}' items must be a list, got {type(items).__name__}",
        )

    # If workflow_ref is set, delegate each iteration to the sub-workflow runner
    if step.workflow_ref:
        from checkpointflow.engine.steps import workflow_ref_step
        from checkpointflow.models.workflow import WorkflowRefStep as WRStep

        ref_results: list[dict[str, Any]] = []
        for i, item in enumerate(items):
            sub_step = WRStep.model_validate(
                {
                    "id": f"{step.id}_iter{i}",
                    "kind": "workflow",
                    "workflow_ref": step.workflow_ref,
                    "inputs": {"_foreach_item": item, "_foreach_index": i},
                }
            )
            sub_ctx = RunContext(
                run_id=ctx.run_id,
                inputs={**ctx.inputs, "_foreach_item": item, "_foreach_index": i},
                step_outputs=ctx.step_outputs,
                run_dir=ctx.run_dir,
                defaults=ctx.defaults,
            )
            result = workflow_ref_step.execute(sub_step, sub_ctx)
            if not result.success:
                return result
            ref_results.append(result.outputs or {})
        return StepResult(success=True, outputs={"iterations": ref_results})

    if not step.body:
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=f"Step '{step.id}' has no body or workflow_ref defined.",
        )

    # Parse body steps
    try:
        body_steps = [_parse_body_step(s) for s in step.body]
    except Exception as exc:
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=f"Step '{step.id}' body parse error: {exc}",
        )

    iterations: list[dict[str, Any]] = []

    for i, item in enumerate(items):
        iteration_outputs: dict[str, Any] = {}

        for body_step in body_steps:
            iter_ctx = RunContext(
                run_id=ctx.run_id,
                inputs={**ctx.inputs, "_foreach_item": item, "_foreach_index": i},
                step_outputs={**ctx.step_outputs, **iteration_outputs},
                run_dir=ctx.run_dir,
                defaults=ctx.defaults,
            )

            if isinstance(body_step, AwaitEventStep):
                return StepResult(
                    success=False,
                    error_code=ErrorCode.ERR_STEP_FAILED,
                    error_message=(
                        f"Step '{step.id}' iteration {i}: "
                        "await_event not supported in foreach body."
                    ),
                )

            if isinstance(body_step, CliStep):
                from checkpointflow.engine.evaluator import interpolate

                # Pre-interpolate ${item} and ${item_index} shorthands
                item_ctx = iter_ctx.build_eval_context()
                item_ctx["item"] = item
                item_ctx["item_index"] = i

                raw_cmd = (
                    " && ".join(body_step.command)
                    if isinstance(body_step.command, list)
                    else body_step.command
                )
                try:
                    resolved_command = interpolate(raw_cmd, item_ctx)
                except EvaluatorError as exc:
                    return StepResult(
                        success=False,
                        error_code=ErrorCode.ERR_STEP_FAILED,
                        error_message=(
                            f"Step '{step.id}' iteration {i} command interpolation failed: {exc}"
                        ),
                    )

                # Create a modified step with the resolved command
                modified_step = body_step.model_copy(
                    update={"command": resolved_command, "id": f"{body_step.id}_iter{i}"}
                )
                result = dispatch_step(modified_step, iter_ctx)
            else:
                result = dispatch_step(body_step, iter_ctx, workflow_steps=list(body_steps))

            if not result.success:
                return StepResult(
                    success=False,
                    error_code=result.error_code,
                    error_message=result.error_message,
                )

            if result.outputs is not None:
                iteration_outputs[body_step.id] = result.outputs

        iterations.append(iteration_outputs)

    return StepResult(success=True, outputs={"iterations": iterations})
