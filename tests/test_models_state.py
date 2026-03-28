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


def test_step_result_success_defaults() -> None:
    result = StepResult(success=True)
    assert result.success is True
    assert result.outputs is None
    assert result.error_code is None
    assert result.error_message is None
    assert result.exit_code is None
