from __future__ import annotations

from pathlib import Path

from checkpointflow.engine.steps.await_event_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import AwaitEventStep


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(run_id="test", inputs={}, step_outputs={}, run_dir=tmp_path)


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


def test_await_event_step_returns_success(tmp_path: Path) -> None:
    assert execute(_step(), _ctx(tmp_path)).success is True


def test_await_event_step_returns_no_outputs(tmp_path: Path) -> None:
    assert execute(_step(), _ctx(tmp_path)).outputs is None


def test_await_event_step_returns_no_error(tmp_path: Path) -> None:
    assert execute(_step(), _ctx(tmp_path)).error_code is None
