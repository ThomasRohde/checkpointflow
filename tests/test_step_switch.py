from __future__ import annotations

from collections.abc import Callable

from checkpointflow.engine.steps.switch_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import SwitchStep


def test_switch_matches_first_case(run_ctx: Callable[..., RunContext]) -> None:
    step = SwitchStep.model_validate(
        {
            "id": "branch",
            "kind": "switch",
            "cases": [
                {"when": 'inputs.mode == "fast"', "next": "fast_path"},
                {"when": 'inputs.mode == "slow"', "next": "slow_path"},
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"mode": "fast"}))
    assert result.success is True
    assert result.outputs == {"_next_step_id": "fast_path"}


def test_switch_matches_second_case(run_ctx: Callable[..., RunContext]) -> None:
    step = SwitchStep.model_validate(
        {
            "id": "branch",
            "kind": "switch",
            "cases": [
                {"when": 'inputs.mode == "fast"', "next": "fast_path"},
                {"when": 'inputs.mode == "slow"', "next": "slow_path"},
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"mode": "slow"}))
    assert result.success is True
    assert result.outputs == {"_next_step_id": "slow_path"}


def test_switch_uses_default_when_no_case_matches(run_ctx: Callable[..., RunContext]) -> None:
    step = SwitchStep.model_validate(
        {
            "id": "branch",
            "kind": "switch",
            "cases": [
                {"when": 'inputs.mode == "fast"', "next": "fast_path"},
            ],
            "default": "fallback",
        }
    )
    result = execute(step, run_ctx(inputs={"mode": "unknown"}))
    assert result.success is True
    assert result.outputs == {"_next_step_id": "fallback"}


def test_switch_fails_when_no_case_and_no_default(run_ctx: Callable[..., RunContext]) -> None:
    step = SwitchStep.model_validate(
        {
            "id": "branch",
            "kind": "switch",
            "cases": [
                {"when": 'inputs.mode == "fast"', "next": "fast_path"},
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"mode": "unknown"}))
    assert result.success is False
    assert result.error_message is not None
    assert "No case matched" in result.error_message


def test_switch_uses_step_outputs_in_condition(run_ctx: Callable[..., RunContext]) -> None:
    step = SwitchStep.model_validate(
        {
            "id": "branch",
            "kind": "switch",
            "cases": [
                {"when": 'steps.check.outputs.status == "ok"', "next": "proceed"},
            ],
            "default": "fail",
        }
    )
    result = execute(
        step,
        run_ctx(inputs={}, step_outputs={"check": {"status": "ok"}}),
    )
    assert result.success is True
    assert result.outputs == {"_next_step_id": "proceed"}
