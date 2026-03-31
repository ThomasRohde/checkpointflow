from __future__ import annotations

from typing import Any

from checkpointflow.engine.evaluator import interpolate_values
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import EndStep


def execute(step: EndStep, ctx: RunContext) -> StepResult:
    result: dict[str, Any] | Any = {}
    if step.result is not None:
        raw = dict(step.result) if isinstance(step.result, dict) else step.result
        eval_ctx = ctx.build_eval_context()
        result = interpolate_values(raw, eval_ctx)
    return StepResult(success=True, outputs=result)
