from __future__ import annotations

from collections.abc import Callable

from checkpointflow.engine.steps.await_event_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import AwaitEventStep


def _step() -> AwaitEventStep:
    return AwaitEventStep.model_validate(
        {
            "id": "approval",
            "kind": "await_event",
            "audience": "user",
            "event_name": "change_approval",
            "input_schema": {"type": "object"},
        }
    )


def test_await_event_step_returns_success(run_ctx: Callable[..., RunContext]) -> None:
    assert execute(_step(), run_ctx()).success is True


def test_await_event_step_returns_no_outputs(run_ctx: Callable[..., RunContext]) -> None:
    assert execute(_step(), run_ctx()).outputs is None


def test_await_event_step_returns_no_error(run_ctx: Callable[..., RunContext]) -> None:
    assert execute(_step(), run_ctx()).error_code is None
