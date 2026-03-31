from __future__ import annotations

from checkpointflow.engine.evaluator import EvaluatorError, evaluate_condition
from checkpointflow.models.errors import ErrorCode
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import SwitchStep


def execute(step: SwitchStep, ctx: RunContext) -> StepResult:
    """Evaluate switch cases and return the target step ID in outputs."""
    eval_ctx = ctx.build_eval_context()
    eval_errors: list[str] = []

    for case in step.cases:
        try:
            if evaluate_condition(case.when, eval_ctx):
                return StepResult(success=True, outputs={"_next_step_id": case.next})
        except EvaluatorError as exc:
            eval_errors.append(f"case '{case.when}': {exc}")
            continue

    if step.default is not None:
        return StepResult(success=True, outputs={"_next_step_id": step.default})

    msg = f"No case matched in switch step '{step.id}' and no default defined."
    if eval_errors:
        msg += f" Evaluation errors: {'; '.join(eval_errors)}"
    return StepResult(
        success=False,
        error_code=ErrorCode.ERR_STEP_FAILED,
        error_message=msg,
    )
