from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from checkpointflow.engine.steps import cli_step, end_step
from checkpointflow.models.errors import ErrorCode
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import CliStep, EndStep, ParallelStep


def _find_step(
    step_id: str,
    workflow_steps: list[Any],
) -> CliStep | EndStep | None:
    """Find a step by ID in the workflow steps list."""
    for s in workflow_steps:
        if s.id == step_id and isinstance(s, (CliStep, EndStep)):
            return s
    return None


def _run_branch(
    step: CliStep | EndStep,
    ctx: RunContext,
) -> StepResult:
    """Execute a single branch step."""
    if isinstance(step, CliStep):
        return cli_step.execute(step, ctx)
    return end_step.execute(step, ctx)


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
    branch_steps: list[tuple[str, CliStep | EndStep]] = []
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
            executor.submit(_run_branch, bstep, ctx): step_id for step_id, bstep in branch_steps
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
