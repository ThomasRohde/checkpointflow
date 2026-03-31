from __future__ import annotations

from collections.abc import Callable
from typing import Any

from checkpointflow.engine.steps.parallel_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import ApiStep, AwaitEventStep, CliStep, ParallelStep


def _make_cli_step(step_id: str, command: str, *, shell: str | None = None) -> CliStep:
    data: dict[str, Any] = {"id": step_id, "kind": "cli", "command": command}
    if shell:
        data["shell"] = shell
    return CliStep.model_validate(data)


def test_parallel_runs_branches(run_ctx: Callable[..., RunContext]) -> None:
    step = ParallelStep.model_validate(
        {
            "id": "par",
            "kind": "parallel",
            "branches": [
                {"start_at": "a"},
                {"start_at": "b"},
            ],
        }
    )
    workflow_steps = [
        _make_cli_step("a", 'echo \'{"from": "a"}\'', shell="bash"),
        _make_cli_step("b", 'echo \'{"from": "b"}\'', shell="bash"),
    ]
    result = execute(step, run_ctx(), workflow_steps=workflow_steps)
    assert result.success is True
    assert result.outputs is not None
    assert "a" in result.outputs
    assert "b" in result.outputs
    assert result.outputs["a"]["from"] == "a"
    assert result.outputs["b"]["from"] == "b"


def test_parallel_branch_failure(run_ctx: Callable[..., RunContext]) -> None:
    step = ParallelStep.model_validate(
        {
            "id": "par",
            "kind": "parallel",
            "branches": [
                {"start_at": "ok"},
                {"start_at": "fail"},
            ],
        }
    )
    workflow_steps = [
        _make_cli_step("ok", "echo ok"),
        _make_cli_step("fail", "exit 1"),
    ]
    result = execute(step, run_ctx(), workflow_steps=workflow_steps)
    assert result.success is False


def test_parallel_branch_not_found(run_ctx: Callable[..., RunContext]) -> None:
    step = ParallelStep.model_validate(
        {
            "id": "par",
            "kind": "parallel",
            "branches": [
                {"start_at": "missing"},
            ],
        }
    )
    result = execute(step, run_ctx(), workflow_steps=[])
    assert result.success is False


def test_parallel_merges_outputs(run_ctx: Callable[..., RunContext]) -> None:
    step = ParallelStep.model_validate(
        {
            "id": "par",
            "kind": "parallel",
            "branches": [
                {"start_at": "x"},
                {"start_at": "y"},
            ],
        }
    )
    workflow_steps = [
        _make_cli_step("x", "echo '{\"val\": 1}'", shell="bash"),
        _make_cli_step("y", "echo '{\"val\": 2}'", shell="bash"),
    ]
    result = execute(step, run_ctx(), workflow_steps=workflow_steps)
    assert result.success is True
    assert result.outputs is not None
    assert result.outputs["x"]["val"] == 1
    assert result.outputs["y"]["val"] == 2


def test_parallel_with_await_event_branch_returns_error(
    run_ctx: Callable[..., RunContext],
) -> None:
    step = ParallelStep.model_validate(
        {
            "id": "par",
            "kind": "parallel",
            "branches": [
                {"start_at": "ok"},
                {"start_at": "evt"},
            ],
        }
    )
    await_step = AwaitEventStep.model_validate(
        {
            "id": "evt",
            "kind": "await_event",
            "audience": "user",
            "event_name": "approval",
            "input_schema": {"type": "object"},
        }
    )
    workflow_steps: list[Any] = [
        _make_cli_step("ok", "echo ok"),
        await_step,
    ]
    result = execute(step, run_ctx(), workflow_steps=workflow_steps)
    assert result.success is False
    assert result.error_message is not None
    assert "await_event" in result.error_message
    assert "not supported" in result.error_message


def test_parallel_all_branches_fail(run_ctx: Callable[..., RunContext]) -> None:
    step = ParallelStep.model_validate(
        {
            "id": "par",
            "kind": "parallel",
            "branches": [
                {"start_at": "fail_a"},
                {"start_at": "fail_b"},
            ],
        }
    )
    workflow_steps = [
        _make_cli_step("fail_a", "exit 1", shell="bash"),
        _make_cli_step("fail_b", "exit 1", shell="bash"),
    ]
    result = execute(step, run_ctx(), workflow_steps=workflow_steps)
    assert result.success is False
    assert result.error_message is not None


def test_parallel_three_branches(run_ctx: Callable[..., RunContext]) -> None:
    step = ParallelStep.model_validate(
        {
            "id": "par",
            "kind": "parallel",
            "branches": [
                {"start_at": "a"},
                {"start_at": "b"},
                {"start_at": "c"},
            ],
        }
    )
    workflow_steps = [
        _make_cli_step("a", 'echo \'{"from": "a"}\'', shell="bash"),
        _make_cli_step("b", 'echo \'{"from": "b"}\'', shell="bash"),
        _make_cli_step("c", 'echo \'{"from": "c"}\'', shell="bash"),
    ]
    result = execute(step, run_ctx(), workflow_steps=workflow_steps)
    assert result.success is True
    assert result.outputs is not None
    assert len(result.outputs) == 3


def test_parallel_with_api_step_branch(run_ctx: Callable[..., RunContext]) -> None:
    step = ParallelStep.model_validate(
        {
            "id": "par",
            "kind": "parallel",
            "branches": [
                {"start_at": "api"},
            ],
        }
    )
    api_step = ApiStep.model_validate(
        {
            "id": "api",
            "kind": "api",
            "method": "GET",
            "url": "http://127.0.0.1:1/unreachable",
        }
    )
    workflow_steps: list[Any] = [api_step]
    result = execute(step, run_ctx(), workflow_steps=workflow_steps)
    assert result.success is False
    assert result.error_message is not None
