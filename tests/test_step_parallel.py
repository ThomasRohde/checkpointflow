from __future__ import annotations

from collections.abc import Callable
from typing import Any

from checkpointflow.engine.steps.parallel_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import CliStep, ParallelStep


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
