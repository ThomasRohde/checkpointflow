from __future__ import annotations

from typing import Any

from checkpointflow.engine.evaluator import interpolate
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import EndStep


def _interpolate_values(value: Any, ctx: dict[str, Any]) -> Any:
    """Recursively interpolate ${...} expressions in string values."""
    if isinstance(value, str) and "${" in value:
        return interpolate(value, ctx)
    if isinstance(value, dict):
        return {k: _interpolate_values(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_values(v, ctx) for v in value]
    return value


def execute(step: EndStep, ctx: RunContext) -> StepResult:
    result: dict[str, Any] | Any = {}
    if step.result is not None:
        raw = dict(step.result) if isinstance(step.result, dict) else step.result
        eval_ctx: dict[str, Any] = {
            "inputs": ctx.inputs,
            "steps": {sid: {"outputs": outs} for sid, outs in ctx.step_outputs.items()},
        }
        result = _interpolate_values(raw, eval_ctx)
    return StepResult(success=True, outputs=result)
