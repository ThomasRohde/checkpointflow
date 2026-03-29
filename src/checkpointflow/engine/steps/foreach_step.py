from __future__ import annotations

from typing import Any

from checkpointflow.engine.evaluator import EvaluatorError, resolve_path
from checkpointflow.engine.steps import cli_step, end_step
from checkpointflow.models.errors import ErrorCode
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import CliStep, EndStep, ForeachStep


def _parse_body_step(step_dict: dict[str, Any]) -> CliStep | EndStep:
    """Parse a body step dict into a Step model."""
    kind = step_dict.get("kind")
    if kind == "cli":
        return CliStep.model_validate(step_dict)
    if kind == "end":
        return EndStep.model_validate(step_dict)
    msg = f"Unsupported body step kind: {kind}"
    raise ValueError(msg)


def execute(step: ForeachStep, ctx: RunContext) -> StepResult:
    """Iterate over items and execute body steps for each."""
    eval_ctx: dict[str, Any] = {
        "inputs": ctx.inputs,
        "steps": {sid: {"outputs": outs} for sid, outs in ctx.step_outputs.items()},
    }

    # Resolve items expression
    items_expr = step.items.strip()
    if items_expr.startswith("${") and items_expr.endswith("}"):
        items_expr = items_expr[2:-1].strip()

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

    if not step.body:
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=f"Step '{step.id}' has no body steps defined.",
        )

    # Parse body steps
    try:
        body_steps = [_parse_body_step(s) for s in step.body]
    except (ValueError, Exception) as exc:
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=f"Step '{step.id}' body parse error: {exc}",
        )

    iterations: list[dict[str, Any]] = []

    for i, item in enumerate(items):
        iteration_outputs: dict[str, Any] = {}

        for body_step in body_steps:
            # Build context with item and item_index available for interpolation
            iter_ctx = RunContext(
                run_id=ctx.run_id,
                inputs=ctx.inputs,
                step_outputs={
                    **ctx.step_outputs,
                    **{sid: outs for sid, outs in iteration_outputs.items()},
                },
                run_dir=ctx.run_dir,
                defaults=ctx.defaults,
            )

            # Inject item and item_index into the eval context by temporarily
            # modifying the context's inputs
            original_inputs = iter_ctx.inputs
            iter_ctx.inputs = {
                **original_inputs,
                "_foreach_item": item,
                "_foreach_index": i,
            }

            # For CLI steps, we need to pre-interpolate item/item_index in the command
            if isinstance(body_step, CliStep):
                from checkpointflow.engine.evaluator import interpolate

                # Build a mini-context for item interpolation
                item_ctx: dict[str, Any] = {
                    "item": item,
                    "item_index": i,
                    "inputs": original_inputs,
                    "steps": {
                        sid: {"outputs": outs}
                        for sid, outs in {
                            **ctx.step_outputs,
                            **iteration_outputs,
                        }.items()
                    },
                }

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
                iter_ctx.inputs = original_inputs
                result = cli_step.execute(modified_step, iter_ctx)
            elif isinstance(body_step, EndStep):
                iter_ctx.inputs = original_inputs
                result = end_step.execute(body_step, iter_ctx)
            else:
                return StepResult(
                    success=False,
                    error_code=ErrorCode.ERR_STEP_FAILED,
                    error_message=f"Step '{step.id}' unsupported body step kind.",
                )

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
