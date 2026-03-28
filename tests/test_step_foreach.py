from __future__ import annotations

from pathlib import Path
from typing import Any

from checkpointflow.engine.steps.foreach_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import ForeachStep


def _ctx(tmp_path: Path, **kwargs: Any) -> RunContext:
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    (run_dir / "stdout").mkdir(exist_ok=True)
    (run_dir / "stderr").mkdir(exist_ok=True)
    return RunContext(
        run_id="test",
        inputs=kwargs.get("inputs", {}),
        step_outputs=kwargs.get("step_outputs", {}),
        run_dir=run_dir,
    )


def test_foreach_iterates_over_items(tmp_path: Path) -> None:
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
    result = execute(step, _ctx(tmp_path, inputs={"names": ["alice", "bob"]}))
    assert result.success is True
    assert result.outputs is not None
    assert len(result.outputs["iterations"]) == 2


def test_foreach_collects_outputs(tmp_path: Path) -> None:
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
                    "outputs": {"type": "object", "properties": {"value": {"type": "string"}}},
                },
            ],
        }
    )
    result = execute(step, _ctx(tmp_path, inputs={"items": ["a", "b"]}))
    assert result.success is True
    assert result.outputs is not None
    iterations = result.outputs["iterations"]
    assert iterations[0]["produce"]["value"] == "a"
    assert iterations[1]["produce"]["value"] == "b"


def test_foreach_empty_items(tmp_path: Path) -> None:
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
    result = execute(step, _ctx(tmp_path, inputs={"items": []}))
    assert result.success is True
    assert result.outputs == {"iterations": []}


def test_foreach_bad_items_expression(tmp_path: Path) -> None:
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
    result = execute(step, _ctx(tmp_path, inputs={}))
    assert result.success is False
    assert result.error_message is not None


def test_foreach_items_not_list(tmp_path: Path) -> None:
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
    result = execute(step, _ctx(tmp_path, inputs={"val": "not-a-list"}))
    assert result.success is False


def test_foreach_step_failure_stops_iteration(tmp_path: Path) -> None:
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
    result = execute(step, _ctx(tmp_path, inputs={"items": ["a", "b"]}))
    assert result.success is False


def test_foreach_provides_item_index(tmp_path: Path) -> None:
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
                    "outputs": {"type": "object", "properties": {"index": {"type": "integer"}}},
                },
            ],
        }
    )
    result = execute(step, _ctx(tmp_path, inputs={"items": ["x", "y"]}))
    assert result.success is True
    assert result.outputs is not None
    assert result.outputs["iterations"][0]["idx"]["index"] == 0
    assert result.outputs["iterations"][1]["idx"]["index"] == 1
