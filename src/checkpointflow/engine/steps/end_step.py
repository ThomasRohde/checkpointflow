from __future__ import annotations

import re
from typing import Any

from checkpointflow.engine.evaluator import interpolate, resolve_path
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import EndStep

_FULL_EXPR = re.compile(r"^\$\{([^}]+)\}$")


def _interpolate_values(value: Any, ctx: dict[str, Any]) -> Any:
    """Recursively interpolate ${...} expressions, preserving types for pure references."""
    if isinstance(value, str) and "${" in value:
        # If the entire string is a single ${expr}, resolve and preserve type
        m = _FULL_EXPR.match(value.strip())
        if m:
            return resolve_path(m.group(1).strip(), ctx)
        # Mixed string: interpolate as string
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
