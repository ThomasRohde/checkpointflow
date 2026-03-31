from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from checkpointflow.models.errors import ErrorCode
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import ParallelStep


def _find_step(
    step_id: str,
    workflow_steps: list[Any],
) -> Any | None:
    """Find a step by ID in the workflow steps list."""
    for s in workflow_steps:
        if s.id == step_id:
            return s
    return None


def _run_branch(
    step: Any,
    ctx: RunContext,
    *,
    workflow_steps: list[Any] | None = None,
) -> StepResult:
    """Execute a single branch step."""
    from checkpointflow.engine.steps.dispatch import dispatch_step
    from checkpointflow.models.workflow import AwaitEventStep

    if isinstance(step, AwaitEventStep):
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message="await_event is not supported in parallel branches.",
        )
    return dispatch_step(step, ctx, workflow_steps=workflow_steps)


def execute(
    step: ParallelStep,
    ctx: RunContext,
    *,
    workflow_steps: list[Any] | None = None,
) -> StepResult:
    """Execute parallel branches concurrently and merge outputs."""
    if workflow_steps is None:
        workflow_steps = []

    # Resolve branch steps
    branch_steps: list[tuple[str, Any]] = []
    for branch in step.branches:
        found = _find_step(branch.start_at, workflow_steps)
        if found is None:
            return StepResult(
                success=False,
                error_code=ErrorCode.ERR_STEP_FAILED,
                error_message=(
                    f"Step '{step.id}' branch target '{branch.start_at}' not found in workflow."
                ),
            )
        branch_steps.append((branch.start_at, found))

    merged_outputs: dict[str, Any] = {}
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=len(branch_steps)) as executor:
        futures = {
            executor.submit(_run_branch, bstep, ctx, workflow_steps=workflow_steps): step_id
            for step_id, bstep in branch_steps
        }
        for future in as_completed(futures):
            step_id = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                errors.append(f"Branch '{step_id}' raised: {exc}")
                continue
            if not result.success:
                errors.append(result.error_message or f"Branch '{step_id}' failed")
                continue
            if result.outputs is not None:
                merged_outputs[step_id] = result.outputs

    if errors:
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=f"Step '{step.id}' parallel branches failed: {'; '.join(errors)}",
        )

    return StepResult(success=True, outputs=merged_outputs)
