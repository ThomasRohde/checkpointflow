from __future__ import annotations

import platform
from collections.abc import Callable
from pathlib import Path

import pytest

from checkpointflow.engine.steps.foreach_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import ForeachStep


def test_foreach_iterates_over_items(run_ctx: Callable[..., RunContext]) -> None:
    step = ForeachStep.model_validate(
        {
            "id": "loop",
            "kind": "foreach",
            "items": "inputs.names",
            "body": [
                {"id": "greet", "kind": "cli", "command": "echo hello ${item}"},
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"names": ["alice", "bob"]}))
    assert result.success is True
    assert result.outputs is not None
    assert len(result.outputs["iterations"]) == 2


def test_foreach_collects_outputs(run_ctx: Callable[..., RunContext]) -> None:
    step = ForeachStep.model_validate(
        {
            "id": "loop",
            "kind": "foreach",
            "items": "inputs.items",
            "body": [
                {
                    "id": "produce",
                    "kind": "cli",
                    "command": 'echo \'{"value": "${item}"}\'',
                    "shell": "bash",
                    "outputs": {"type": "object", "properties": {"value": {"type": "string"}}},
                },
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"items": ["a", "b"]}))
    assert result.success is True
    assert result.outputs is not None
    iterations = result.outputs["iterations"]
    assert iterations[0]["produce"]["value"] == "a"
    assert iterations[1]["produce"]["value"] == "b"


def test_foreach_empty_items(run_ctx: Callable[..., RunContext]) -> None:
    step = ForeachStep.model_validate(
        {
            "id": "loop",
            "kind": "foreach",
            "items": "inputs.items",
            "body": [
                {"id": "noop", "kind": "cli", "command": "echo noop"},
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"items": []}))
    assert result.success is True
    assert result.outputs == {"iterations": []}


def test_foreach_bad_items_expression(run_ctx: Callable[..., RunContext]) -> None:
    step = ForeachStep.model_validate(
        {
            "id": "loop",
            "kind": "foreach",
            "items": "inputs.nonexistent",
            "body": [
                {"id": "noop", "kind": "cli", "command": "echo noop"},
            ],
        }
    )
    result = execute(step, run_ctx(inputs={}))
    assert result.success is False
    assert result.error_message is not None


def test_foreach_items_not_list(run_ctx: Callable[..., RunContext]) -> None:
    step = ForeachStep.model_validate(
        {
            "id": "loop",
            "kind": "foreach",
            "items": "inputs.val",
            "body": [
                {"id": "noop", "kind": "cli", "command": "echo noop"},
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"val": "not-a-list"}))
    assert result.success is False


def test_foreach_step_failure_stops_iteration(run_ctx: Callable[..., RunContext]) -> None:
    step = ForeachStep.model_validate(
        {
            "id": "loop",
            "kind": "foreach",
            "items": "inputs.items",
            "body": [
                {"id": "fail", "kind": "cli", "command": "exit 1"},
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"items": ["a", "b"]}))
    assert result.success is False


def test_foreach_provides_item_index(run_ctx: Callable[..., RunContext]) -> None:
    step = ForeachStep.model_validate(
        {
            "id": "loop",
            "kind": "foreach",
            "items": "inputs.items",
            "body": [
                {
                    "id": "idx",
                    "kind": "cli",
                    "command": "echo '{\"index\": ${item_index}}'",
                    "shell": "bash",
                    "outputs": {"type": "object", "properties": {"index": {"type": "integer"}}},
                },
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"items": ["x", "y"]}))
    assert result.success is True
    assert result.outputs is not None
    assert result.outputs["iterations"][0]["idx"]["index"] == 0
    assert result.outputs["iterations"][1]["idx"]["index"] == 1


def test_foreach_with_workflow_ref(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    """foreach with workflow_ref runs a sub-workflow per item."""
    sub_wf = tmp_path / "sub.yaml"
    sub_wf.write_text(
        "schema_version: checkpointflow/v1\n"
        "workflow:\n"
        "  id: sub\n"
        "  inputs:\n"
        "    type: object\n"
        "  steps:\n"
        "    - id: step1\n"
        "      kind: cli\n"
        "      command: echo hello\n"
        "    - id: done\n"
        "      kind: end\n"
    )
    step = ForeachStep.model_validate(
        {
            "id": "loop",
            "kind": "foreach",
            "items": "inputs.items",
            "workflow_ref": str(sub_wf),
        }
    )
    result = execute(step, run_ctx(inputs={"items": ["a", "b"]}))
    assert result.success is True
    assert result.outputs is not None
    assert len(result.outputs["iterations"]) == 2


def test_foreach_body_with_await_event_returns_error(
    run_ctx: Callable[..., RunContext],
) -> None:
    """await_event steps are not supported in foreach body."""
    step = ForeachStep.model_validate(
        {
            "id": "loop",
            "kind": "foreach",
            "items": "inputs.items",
            "body": [
                {
                    "id": "wait",
                    "kind": "await_event",
                    "audience": "user",
                    "event_name": "approval",
                    "input_schema": {"type": "object"},
                },
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"items": ["a"]}))
    assert result.success is False
    assert result.error_message is not None
    assert "await_event not supported in foreach body" in result.error_message


def test_foreach_body_with_api_step(run_ctx: Callable[..., RunContext]) -> None:
    """An api body step dispatches correctly; connection error propagates as failure."""
    step = ForeachStep.model_validate(
        {
            "id": "loop",
            "kind": "foreach",
            "items": "inputs.items",
            "body": [
                {
                    "id": "call",
                    "kind": "api",
                    "method": "GET",
                    "url": "http://127.0.0.1:1/unreachable",
                },
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"items": ["x"]}))
    assert result.success is False
    assert result.error_message is not None


@pytest.mark.skipif(platform.system() != "Windows", reason="echo syntax is platform-specific")
def test_foreach_body_with_nested_foreach(run_ctx: Callable[..., RunContext]) -> None:
    """A foreach body can contain another foreach step."""
    step = ForeachStep.model_validate(
        {
            "id": "outer",
            "kind": "foreach",
            "items": "inputs.matrix",
            "body": [
                {
                    "id": "inner",
                    "kind": "foreach",
                    "items": "inputs._foreach_item",
                    "body": [
                        {
                            "id": "echo",
                            "kind": "cli",
                            "command": "echo ${item}",
                        },
                    ],
                },
            ],
        }
    )
    result = execute(step, run_ctx(inputs={"matrix": [["a", "b"], ["c"]]}))
    assert result.success is True
    assert result.outputs is not None
    outer_iters = result.outputs["iterations"]
    assert len(outer_iters) == 2
    # Each outer iteration has an "inner" key with its own iterations
    inner_0 = outer_iters[0]["inner"]["iterations"]
    inner_1 = outer_iters[1]["inner"]["iterations"]
    assert len(inner_0) == 2
    assert len(inner_1) == 1
