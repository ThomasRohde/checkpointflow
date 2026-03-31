from __future__ import annotations

from collections.abc import Callable

from checkpointflow.engine.steps.end_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import EndStep


def test_end_step_returns_success(run_ctx: Callable[..., RunContext]) -> None:
    step = EndStep.model_validate({"id": "done", "kind": "end"})
    result = execute(step, run_ctx())
    assert result.success is True


def test_end_step_with_result(run_ctx: Callable[..., RunContext]) -> None:
    step = EndStep.model_validate({"id": "done", "kind": "end", "result": {"status": "rejected"}})
    result = execute(step, run_ctx())
    assert result.outputs == {"status": "rejected"}


def test_end_step_without_result(run_ctx: Callable[..., RunContext]) -> None:
    step = EndStep.model_validate({"id": "done", "kind": "end"})
    result = execute(step, run_ctx())
    assert result.outputs == {}
