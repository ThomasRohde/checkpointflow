from __future__ import annotations

from typing import Any

from checkpointflow.engine.evaluator import EvaluatorError, evaluate_condition
from checkpointflow.models.errors import ErrorCode
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import SwitchStep


def execute(step: SwitchStep, ctx: RunContext) -> StepResult:
    """Evaluate switch cases and return the target step ID in outputs."""
    eval_ctx: dict[str, Any] = {
        "inputs": ctx.inputs,
        "steps": {sid: {"outputs": outs} for sid, outs in ctx.step_outputs.items()},
    }

    for case in step.cases:
        try:
            if evaluate_condition(case.when, eval_ctx):
                return StepResult(success=True, outputs={"_next_step_id": case.next})
        except EvaluatorError:
            continue

    if step.default is not None:
        return StepResult(success=True, outputs={"_next_step_id": step.default})

    return StepResult(
        success=False,
        error_code=ErrorCode.ERR_STEP_FAILED,
        error_message=f"No case matched in switch step '{step.id}' and no default defined.",
    )
