"""Unified step dispatcher — routes any step kind to its handler."""

from __future__ import annotations

from typing import Any

from checkpointflow.engine.steps import (
    api_step,
    await_event_step,
    cli_step,
    end_step,
    foreach_step,
    parallel_step,
    switch_step,
    workflow_ref_step,
)
from checkpointflow.models.errors import ErrorCode
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import (
    ApiStep,
    AwaitEventStep,
    CliStep,
    EndStep,
    ForeachStep,
    ParallelStep,
    SwitchStep,
    WorkflowRefStep,
)


def dispatch_step(
    step: CliStep
    | ApiStep
    | AwaitEventStep
    | EndStep
    | ForeachStep
    | ParallelStep
    | SwitchStep
    | WorkflowRefStep,
    ctx: RunContext,
    *,
    workflow_steps: list[Any] | None = None,
) -> StepResult:
    """Dispatch a step to its handler and return the result."""
    if isinstance(step, CliStep):
        return cli_step.execute(step, ctx)
    if isinstance(step, EndStep):
        return end_step.execute(step, ctx)
    if isinstance(step, AwaitEventStep):
        return await_event_step.execute(step, ctx)
    if isinstance(step, ApiStep):
        return api_step.execute(step, ctx)
    if isinstance(step, SwitchStep):
        return switch_step.execute(step, ctx)
    if isinstance(step, ForeachStep):
        return foreach_step.execute(step, ctx)
    if isinstance(step, ParallelStep):
        return parallel_step.execute(step, ctx, workflow_steps=workflow_steps or [])
    if isinstance(step, WorkflowRefStep):
        return workflow_ref_step.execute(step, ctx)
    return StepResult(
        success=False,
        error_code=ErrorCode.ERR_UNSUPPORTED_STEP,
        error_message=f"Unsupported step kind: {getattr(step, 'kind', 'unknown')}",
    )
