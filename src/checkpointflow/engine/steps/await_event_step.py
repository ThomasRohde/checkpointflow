from __future__ import annotations

from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import AwaitEventStep


def execute(step: AwaitEventStep, ctx: RunContext) -> StepResult:
    return StepResult(success=True)
