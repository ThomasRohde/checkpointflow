"""Tests for the unified step dispatcher."""

from __future__ import annotations

from collections.abc import Callable

from checkpointflow.engine.steps.dispatch import dispatch_step
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import (
    AwaitEventStep,
    CliStep,
    EndStep,
    SwitchStep,
)


def test_dispatch_cli_step(run_ctx: Callable[..., RunContext]) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "echo hello"})
    result = dispatch_step(step, run_ctx())
    assert result.success is True


def test_dispatch_end_step(run_ctx: Callable[..., RunContext]) -> None:
    step = EndStep.model_validate({"id": "done", "kind": "end", "result": {"ok": True}})
    result = dispatch_step(step, run_ctx())
    assert result.success is True
    assert result.outputs == {"ok": True}


def test_dispatch_await_event_step(run_ctx: Callable[..., RunContext]) -> None:
    step = AwaitEventStep.model_validate(
        {
            "id": "wait",
            "kind": "await_event",
            "audience": "user",
            "event_name": "approval",
            "input_schema": {"type": "object"},
        }
    )
    result = dispatch_step(step, run_ctx())
    assert result.success is True


def test_dispatch_switch_step(run_ctx: Callable[..., RunContext]) -> None:
    step = SwitchStep.model_validate(
        {
            "id": "branch",
            "kind": "switch",
            "cases": [{"when": 'inputs.x == "a"', "next": "target"}],
            "default": "fallback",
        }
    )
    result = dispatch_step(step, run_ctx(inputs={"x": "a"}))
    assert result.success is True
    assert result.outputs == {"_next_step_id": "target"}


def test_dispatch_returns_step_result(run_ctx: Callable[..., RunContext]) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "echo hi"})
    result = dispatch_step(step, run_ctx())
    assert isinstance(result, StepResult)
