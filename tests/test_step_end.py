from __future__ import annotations

from pathlib import Path

from checkpointflow.engine.steps.end_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import EndStep


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(
        run_id="test",
        inputs={},
        step_outputs={},
        run_dir=tmp_path,
    )


def test_end_step_returns_success(tmp_path: Path) -> None:
    step = EndStep.model_validate({"id": "done", "kind": "end"})
    result = execute(step, _ctx(tmp_path))
    assert result.success is True


def test_end_step_with_result(tmp_path: Path) -> None:
    step = EndStep.model_validate({"id": "done", "kind": "end", "result": {"status": "rejected"}})
    result = execute(step, _ctx(tmp_path))
    assert result.outputs == {"status": "rejected"}


def test_end_step_without_result(tmp_path: Path) -> None:
    step = EndStep.model_validate({"id": "done", "kind": "end"})
    result = execute(step, _ctx(tmp_path))
    assert result.outputs == {}
