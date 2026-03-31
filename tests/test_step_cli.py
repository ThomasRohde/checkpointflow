from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from checkpointflow.engine.steps.cli_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import CliStep, Success


def test_cli_step_runs_echo(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "echo hello"})
    result = execute(step, run_ctx())
    assert result.success is True
    assert result.exit_code == 0


def test_cli_step_captures_stdout(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "echo hello"})
    execute(step, run_ctx())
    stdout_file = tmp_path / "stdout" / "s1.txt"
    assert stdout_file.exists()
    assert "hello" in stdout_file.read_text()


def test_cli_step_nonzero_exit_fails(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "exit 1"})
    result = execute(step, run_ctx())
    assert result.success is False
    assert result.error_code == "ERR_STEP_FAILED"
    assert result.exit_code == 1


def test_cli_step_custom_success_exit_codes(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
    step = CliStep(
        id="s1",
        kind="cli",
        command="exit 1",
        success=Success(exit_codes=[0, 1]),
    )
    result = execute(step, run_ctx())
    assert result.success is True


def test_cli_step_parses_json_stdout(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    step = CliStep.model_validate(
        {
            "id": "s1",
            "kind": "cli",
            "command": """python -c "import json; print(json.dumps({'key':'val'}))" """,
        }
    )
    result = execute(step, run_ctx())
    assert result.success is True
    assert result.outputs == {"key": "val"}


def test_cli_step_non_json_stdout(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "echo not-json"})
    result = execute(step, run_ctx())
    assert result.success is True
    assert result.outputs is None


def test_cli_step_validates_output_schema_pass(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
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
    result = execute(step, run_ctx())
    assert result.success is True
    assert result.outputs == {"name": "Alice"}


def test_cli_step_validates_output_schema_fail(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
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
    result = execute(step, run_ctx())
    assert result.success is False
    assert result.error_code == "ERR_STEP_OUTPUT_INVALID"


def test_cli_step_interpolates_command(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "echo ${inputs.name}"})
    ctx = run_ctx(inputs={"name": "world"})
    result = execute(step, ctx)
    assert result.success is True
    stdout_file = tmp_path / "stdout" / "s1.txt"
    assert "world" in stdout_file.read_text()


def test_cli_step_timeout(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    step = CliStep.model_validate(
        {
            "id": "s1",
            "kind": "cli",
            "command": "sleep 10",
            "timeout_seconds": 1,
        }
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert result.error_code == "ERR_TIMEOUT"


def test_cli_step_writes_stderr_file(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    step = CliStep.model_validate({"id": "s1", "kind": "cli", "command": "echo err >&2"})
    execute(step, run_ctx())
    stderr_file = tmp_path / "stderr" / "s1.txt"
    assert stderr_file.exists()


def test_cli_step_non_json_with_outputs_schema_fails(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
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
    result = execute(step, run_ctx())
    assert result.success is False
    assert result.error_code == "ERR_STEP_OUTPUT_INVALID"


def test_cli_step_command_as_list(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    """command can be a list of strings, joined with && at runtime."""
    step = CliStep.model_validate(
        {
            "id": "multi",
            "kind": "cli",
            "command": ["echo hello", "echo world"],
            "shell": "bash",
        }
    )
    result = execute(step, run_ctx())
    assert result.success is True
    stdout = (tmp_path / "stdout" / "multi.txt").read_text()
    assert "hello" in stdout
    assert "world" in stdout


def test_cli_step_command_list_stops_on_failure(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
    """If one command in the list fails, subsequent ones do not run."""
    step = CliStep.model_validate(
        {
            "id": "fail_mid",
            "kind": "cli",
            "command": ["echo before", "exit 1", "echo after"],
            "shell": "bash",
        }
    )
    result = execute(step, run_ctx())
    assert result.success is False
    stdout = (tmp_path / "stdout" / "fail_mid.txt").read_text()
    assert "before" in stdout
    assert "after" not in stdout


def test_cli_step_command_list_single_element(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
    step = CliStep.model_validate({"id": "one", "kind": "cli", "command": ["echo solo"]})
    result = execute(step, run_ctx())
    assert result.success is True


def test_cli_step_command_list_with_interpolation(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
    step = CliStep.model_validate(
        {
            "id": "interp",
            "kind": "cli",
            "command": ["echo ${inputs.name}", "echo done"],
            "shell": "bash",
        }
    )
    result = execute(step, run_ctx(inputs={"name": "test"}))
    assert result.success is True
    stdout = (tmp_path / "stdout" / "interp.txt").read_text()
    assert "test" in stdout
    assert "done" in stdout


# --- Shell allow-list ---


def test_cli_step_rejects_unknown_shell(tmp_path: Path, run_ctx: Callable[..., RunContext]) -> None:
    step = CliStep.model_validate(
        {"id": "s1", "kind": "cli", "command": "echo hi", "shell": "/usr/local/evil"}
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert "unsupported shell" in (result.error_message or "").lower()


def test_cli_step_rejects_arbitrary_executable(
    tmp_path: Path, run_ctx: Callable[..., RunContext]
) -> None:
    step = CliStep.model_validate(
        {"id": "s1", "kind": "cli", "command": "echo hi", "shell": "python3"}
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert "unsupported shell" in (result.error_message or "").lower()
