from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

from checkpointflow.engine.runner import run_workflow
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


def test_switch_deep_chain_no_recursion_error(tmp_path: Path) -> None:
    """Ensure a long chain of switch steps doesn't hit Python's recursion limit."""
    # Temporarily lower the recursion limit so a smaller chain still proves
    # that the iterative implementation works where recursion would fail.
    original_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(100)
    try:
        n = 150
        _run_deep_switch_chain(tmp_path, n)
    finally:
        sys.setrecursionlimit(original_limit)


def _run_deep_switch_chain(tmp_path: Path, n: int) -> None:
    steps: list[dict[str, object]] = []
    for i in range(n):
        next_id = f"switch_{i + 1}" if i < n - 1 else "done"
        steps.append(
            {
                "id": f"switch_{i}",
                "kind": "switch",
                "cases": [{"when": 'inputs.go == "yes"', "next": next_id}],
            }
        )
    steps.append({"id": "done", "kind": "end", "result": {"status": "ok"}})

    workflow = {
        "schema_version": "checkpointflow/v1",
        "workflow": {
            "id": "deep_switch",
            "version": "1.0",
            "inputs": {"type": "object", "properties": {"go": {"type": "string"}}},
            "steps": steps,
        },
    }
    import yaml

    wf_path = tmp_path / "deep_switch.yaml"
    wf_path.write_text(yaml.dump(workflow), encoding="utf-8")

    envelope = run_workflow(wf_path, json.dumps({"go": "yes"}), base_dir=tmp_path)
    assert envelope.ok is True
    assert envelope.status == "completed"
    assert envelope.result == {"status": "ok"}


def test_switch_malformed_condition_surfaces_in_error(run_ctx: Callable[..., RunContext]) -> None:
    """When a case has a malformed condition and no case matches, the error message explains why."""
    step = SwitchStep.model_validate(
        {
            "id": "branch",
            "kind": "switch",
            "cases": [
                {"when": "!!!invalid expression!!!", "next": "broken_path"},
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"mode": "test"}))
    assert result.success is False
    assert result.error_message is not None
    assert (
        "evaluation error" in result.error_message.lower()
        or "invalid" in result.error_message.lower()
    )


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
