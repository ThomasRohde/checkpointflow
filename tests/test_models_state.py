from __future__ import annotations

from pathlib import Path

from checkpointflow.models.state import RunContext, StepResult


def test_run_context_fields(tmp_path: Path) -> None:
    ctx = RunContext(
        run_id="abc123",
        inputs={"name": "Alice"},
        step_outputs={},
        run_dir=tmp_path,
    )
    assert ctx.run_id == "abc123"
    assert ctx.inputs["name"] == "Alice"
    assert ctx.step_outputs == {}
    assert ctx.run_dir == tmp_path


def test_run_context_build_eval_context(tmp_path: Path) -> None:
    ctx = RunContext(
        run_id="r1",
        inputs={"name": "Alice"},
        step_outputs={"s1": {"key": "val"}},
        run_dir=tmp_path,
    )
    eval_ctx = ctx.build_eval_context()
    assert eval_ctx == {
        "inputs": {"name": "Alice"},
        "steps": {"s1": {"outputs": {"key": "val"}}},
    }


def test_run_context_build_eval_context_with_event(tmp_path: Path) -> None:
    ctx = RunContext(
        run_id="r1",
        inputs={"name": "Alice"},
        step_outputs={"s1": {"key": "val"}},
        run_dir=tmp_path,
    )
    event = {"decision": "approve"}
    eval_ctx = ctx.build_eval_context(event=event)
    assert eval_ctx["event"] == {"decision": "approve"}
    assert eval_ctx["inputs"] == {"name": "Alice"}


def test_run_context_build_eval_context_without_event_has_no_event_key(tmp_path: Path) -> None:
    ctx = RunContext(run_id="r1", inputs={}, step_outputs={}, run_dir=tmp_path)
    eval_ctx = ctx.build_eval_context()
    assert "event" not in eval_ctx


def test_run_context_build_eval_context_empty(tmp_path: Path) -> None:
    ctx = RunContext(run_id="r1", inputs={}, step_outputs={}, run_dir=tmp_path)
    eval_ctx = ctx.build_eval_context()
    assert eval_ctx == {"inputs": {}, "steps": {}}


def test_step_result_success_defaults() -> None:
    result = StepResult(success=True)
    assert result.success is True
    assert result.outputs is None
    assert result.error_code is None
    assert result.error_message is None
    assert result.exit_code is None
