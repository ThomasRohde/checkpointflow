"""Coverage gap tests: edge cases, invariants, and regression prevention."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from checkpointflow.cli import app
from checkpointflow.engine.evaluator import EvaluatorError, evaluate_condition
from checkpointflow.engine.runner import resume_workflow, run_workflow
from checkpointflow.models.workflow import EndStep

runner = CliRunner()


# --- Example workflow validation ---


def test_simple_echo_example_validates() -> None:
    result = runner.invoke(app, ["validate", "-f", "examples/simple-echo.yaml"])
    assert result.exit_code == 0


def test_conditional_steps_example_validates() -> None:
    result = runner.invoke(app, ["validate", "-f", "examples/conditional-steps.yaml"])
    assert result.exit_code == 0


def test_agent_decision_example_validates() -> None:
    result = runner.invoke(app, ["validate", "-f", "examples/agent-decision.yaml"])
    assert result.exit_code == 0


def test_simple_echo_runs_to_completion(tmp_path: Path) -> None:
    env = run_workflow(
        Path("examples/simple-echo.yaml"),
        '{"name":"World"}',
        base_dir=tmp_path / "store",
    )
    assert env.ok is True
    assert env.status == "completed"


# --- End step edge cases ---


def test_end_step_with_scalar_result(tmp_path: Path) -> None:
    step = EndStep.model_validate({"id": "done", "kind": "end", "result": "finished"})
    from checkpointflow.engine.steps.end_step import execute
    from checkpointflow.models.state import RunContext

    ctx = RunContext(run_id="test", inputs={}, step_outputs={}, run_dir=tmp_path)
    result = execute(step, ctx)
    assert result.success is True
    assert result.outputs == "finished"


# --- Evaluator edge cases ---


def test_evaluate_condition_whitespace_only_raises() -> None:
    with pytest.raises(EvaluatorError):
        evaluate_condition("   ", {})


# --- Invariant: exit code 40 never on failure ---


def test_exit_40_only_on_waiting(tmp_path: Path) -> None:
    """Step failure should never produce exit code 40."""
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: fail
      kind: cli
      command: exit 1
    - id: done
      kind: end
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.exit_code != 40


# --- Double resume ---


def test_double_resume_second_fails(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: wait
      kind: await_event
      audience: user
      event_name: ev
      input_schema:
        type: object
    - id: done
      kind: end
""")
    env1 = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env1.run_id is not None

    # First resume succeeds
    env2 = resume_workflow(env1.run_id, "ev", "{}", base_dir=tmp_path / "store")
    assert env2.ok is True

    # Second resume fails (no longer waiting)
    env3 = resume_workflow(env1.run_id, "ev", "{}", base_dir=tmp_path / "store")
    assert env3.ok is False
    assert env3.error is not None
    assert env3.error.code == "ERR_RUN_NOT_WAITING"


# --- All CLI commands in help ---


def test_all_commands_in_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("validate", "run", "resume", "status", "inspect", "guide", "init", "cancel"):
        assert cmd in result.stdout, f"Command '{cmd}' missing from --help output"


# --- Resume with deleted workflow ---


def test_resume_deleted_workflow_errors(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: wait
      kind: await_event
      audience: user
      event_name: ev
      input_schema:
        type: object
    - id: done
      kind: end
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None

    # Delete the workflow file
    wf.unlink()

    env2 = resume_workflow(env.run_id, "ev", "{}", base_dir=tmp_path / "store")
    assert env2.ok is False


# --- Blackbox bug fixes ---


def test_init_nonexistent_directory_returns_envelope(tmp_path: Path) -> None:
    """Bug #1: init to non-existent dir should return envelope, not crash."""
    result = runner.invoke(
        app, ["init", "--file", str(tmp_path / "no" / "such" / "dir" / "wf.yaml")]
    )
    assert result.exit_code != 0
    import json

    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False


def test_init_file_exists_uses_correct_error_code(tmp_path: Path) -> None:
    """Bug #7: should use ERR_FILE_EXISTS, not ERR_FILE_NOT_FOUND."""
    out = tmp_path / "existing.yaml"
    out.write_text("old")
    result = runner.invoke(app, ["init", "--file", str(out)])
    import json

    envelope = json.loads(result.stdout)
    assert envelope["error"]["code"] == "ERR_FILE_EXISTS"


def test_validate_directory_gives_clear_error(tmp_path: Path) -> None:
    """Bug: validate -f <dir> should say 'expected a file', not ERR_INTERNAL."""
    result = runner.invoke(app, ["validate", "-f", str(tmp_path)])
    import json

    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] != "ERR_INTERNAL"
    assert "directory" in envelope["error"]["message"].lower()


def test_validate_duplicate_step_ids_rejected(tmp_path: Path) -> None:
    """Bug #8: duplicate step IDs should be rejected."""
    wf = tmp_path / "dup.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: step1
      kind: cli
      command: echo a
    - id: step1
      kind: cli
      command: echo b
    - id: done
      kind: end
""")
    result = runner.invoke(app, ["validate", "-f", str(wf)])
    assert result.exit_code == 10
    import json

    envelope = json.loads(result.stdout)
    assert envelope["error"]["code"] == "ERR_DUPLICATE_STEP_ID"
