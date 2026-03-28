from __future__ import annotations

from pathlib import Path

from checkpointflow.engine.steps.cli_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import CliStep, Success


def _ctx(tmp_path: Path, **kwargs: object) -> RunContext:
    (tmp_path / "stdout").mkdir(exist_ok=True)
    (tmp_path / "stderr").mkdir(exist_ok=True)
    return RunContext(
        run_id="test",
        inputs=kwargs.get("inputs", {}),  # type: ignore[arg-type]
        step_outputs=kwargs.get("step_outputs", {}),  # type: ignore[arg-type]
        run_dir=tmp_path,
    )


def test_cli_step_runs_echo(tmp_path: Path) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "echo hello"})
    result = execute(step, _ctx(tmp_path))
    assert result.success is True
    assert result.exit_code == 0


def test_cli_step_captures_stdout(tmp_path: Path) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "echo hello"})
    execute(step, _ctx(tmp_path))
    stdout_file = tmp_path / "stdout" / "s1.txt"
    assert stdout_file.exists()
    assert "hello" in stdout_file.read_text()


def test_cli_step_nonzero_exit_fails(tmp_path: Path) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "exit 1"})
    result = execute(step, _ctx(tmp_path))
    assert result.success is False
    assert result.error_code == "ERR_STEP_FAILED"
    assert result.exit_code == 1


def test_cli_step_custom_success_exit_codes(tmp_path: Path) -> None:
    step = CliStep(
        id="s1",
        kind="cli",
        command="exit 1",
        success=Success(exit_codes=[0, 1]),
    )
    result = execute(step, _ctx(tmp_path))
    assert result.success is True


def test_cli_step_parses_json_stdout(tmp_path: Path) -> None:
    step = CliStep.model_validate(
        {
            "id": "s1",
            "kind": "cli",
            "command": """python -c "import json; print(json.dumps({'key':'val'}))" """,
        }
    )
    result = execute(step, _ctx(tmp_path))
    assert result.success is True
    assert result.outputs == {"key": "val"}


def test_cli_step_non_json_stdout(tmp_path: Path) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "echo not-json"})
    result = execute(step, _ctx(tmp_path))
    assert result.success is True
    assert result.outputs is None


def test_cli_step_validates_output_schema_pass(tmp_path: Path) -> None:
    step = CliStep.model_validate(
        {
            "id": "s1",
            "kind": "cli",
            "command": ("""python -c "import json; print(json.dumps({'name':'Alice'}))" """),
            "outputs": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            },
        }
    )
    result = execute(step, _ctx(tmp_path))
    assert result.success is True
    assert result.outputs == {"name": "Alice"}


def test_cli_step_validates_output_schema_fail(tmp_path: Path) -> None:
    step = CliStep.model_validate(
        {
            "id": "s1",
            "kind": "cli",
            "command": ("""python -c "import json; print(json.dumps({'name':123}))" """),
            "outputs": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            },
        }
    )
    result = execute(step, _ctx(tmp_path))
    assert result.success is False
    assert result.error_code == "ERR_STEP_OUTPUT_INVALID"


def test_cli_step_interpolates_command(tmp_path: Path) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "echo ${inputs.name}"})
    ctx = _ctx(tmp_path, inputs={"name": "world"})
    result = execute(step, ctx)
    assert result.success is True
    stdout_file = tmp_path / "stdout" / "s1.txt"
    assert "world" in stdout_file.read_text()


def test_cli_step_timeout(tmp_path: Path) -> None:
    step = CliStep.model_validate(
        {
            "id": "s1",
            "kind": "cli",
            "command": "sleep 10",
            "timeout_seconds": 1,
        }
    )
    result = execute(step, _ctx(tmp_path))
    assert result.success is False
    assert result.error_code == "ERR_TIMEOUT"


def test_cli_step_writes_stderr_file(tmp_path: Path) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "echo err >&2"})
    execute(step, _ctx(tmp_path))
    stderr_file = tmp_path / "stderr" / "s1.txt"
    assert stderr_file.exists()


def test_cli_step_non_json_with_outputs_schema_fails(tmp_path: Path) -> None:
    step = CliStep.model_validate(
        {
            "id": "s1",
            "kind": "cli",
            "command": "echo not-json",
            "outputs": {
                "type": "object",
                "required": ["key"],
                "properties": {"key": {"type": "string"}},
            },
        }
    )
    result = execute(step, _ctx(tmp_path))
    assert result.success is False
    assert result.error_code == "ERR_STEP_OUTPUT_INVALID"
