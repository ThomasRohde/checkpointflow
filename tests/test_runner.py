from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from checkpointflow.engine.runner import run_workflow


def _write_input(tmp_path: Path, data: dict[str, object]) -> Path:
    p = tmp_path / "input.json"
    p.write_text(json.dumps(data))
    return p


# --- Input parsing ---


def test_run_inline_input(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True


def test_run_file_input(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    inp = _write_input(tmp_path, {})
    env = run_workflow(wf, f"@{inp}", base_dir=tmp_path / "store")
    assert env.ok is True


def test_run_invalid_json_input(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{bad", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == "ERR_VALIDATION_INPUT"


def test_run_input_file_not_found(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "@nope.json", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == "ERR_FILE_NOT_FOUND"


def test_run_input_schema_validation(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
        inputs_schema=(
            "type: object\n    required: [name]\n    properties:\n      name:\n        type: string"
        ),
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == "ERR_VALIDATION_INPUT"


# --- Execution ---


def test_run_single_end_step(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.status == "completed"
    assert env.exit_code == 0


def test_run_cli_then_end(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: greet
      kind: cli
      command: echo hello
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.status == "completed"


def test_run_step_outputs_forwarded(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: step1
      kind: cli
      command: 'python -c "import json; print(json.dumps({''val'':''hello''}))"'
    - id: step2
      kind: cli
      command: echo ${steps.step1.outputs.val}
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True


def test_run_skip_step_with_false_if(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: skipped
      kind: cli
      command: exit 1
      if: inputs.run_it == "yes"
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, '{"run_it":"no"}', base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.status == "completed"


def test_run_step_with_true_if(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: run_me
      kind: cli
      command: echo ran
      if: inputs.go == "yes"
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, '{"go":"yes"}', base_dir=tmp_path / "store")
    assert env.ok is True


def test_run_cli_failure_stops(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: fail_step
      kind: cli
      command: exit 1
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.exit_code == 30
    assert env.error is not None
    assert env.error.code == "ERR_STEP_FAILED"


def test_run_api_step_connection_failure(
    tmp_path: Path, write_workflow: Callable[..., Path]
) -> None:
    """API steps are now supported; a connection error results in step failure (exit 30)."""
    wf = write_workflow(
        """\
    - id: call_api
      kind: api
      method: GET
      url: http://127.0.0.1:1/unreachable
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.exit_code == 30


# --- Persistence ---


def test_run_envelope_has_run_id(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None
    assert len(env.run_id) > 0


def test_run_envelope_has_workflow_id(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.workflow_id == "test_wf"
    assert env.workflow_version == "1.0"


def test_run_envelope_has_workflow_name_and_description(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: named_wf
  name: Named Workflow
  description: A workflow with a name and description
  version: "2.0"
  inputs:
    type: object
  steps:
    - id: done
      kind: end
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.workflow_name == "Named Workflow"
    assert env.workflow_description == "A workflow with a name and description"


def test_run_envelope_omits_workflow_name_when_not_set(
    tmp_path: Path, write_workflow: Callable[..., Path]
) -> None:
    wf = write_workflow(
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.workflow_name is None
    assert env.workflow_description is None


# --- _parse_input path traversal ---


def test_parse_input_rejects_traversal() -> None:
    import pytest

    from checkpointflow.engine.runner import _parse_input

    with pytest.raises(ValueError, match="traversal"):
        _parse_input("@../../etc/passwd")


def test_parse_input_allows_absolute_path(tmp_path: Path) -> None:
    from checkpointflow.engine.runner import _parse_input

    f = tmp_path / "data.json"
    f.write_text('{"key": "val"}')
    result = _parse_input(f"@{f}")
    assert result == {"key": "val"}


def test_run_workflow_internal_error_returns_exit_code_90(
    tmp_path: Path, write_workflow: Callable[..., Path]
) -> None:
    """The catch-all except Exception handler wraps unexpected errors in ERR_INTERNAL."""
    from unittest.mock import patch

    from checkpointflow.models.errors import ExitCode

    wf = write_workflow("- id: greet\n  kind: cli\n  command: echo hi")

    with patch(
        "checkpointflow.engine.runner._run_workflow_inner",
        side_effect=RuntimeError("boom"),
    ):
        env = run_workflow(wf, "{}", base_dir=tmp_path / "store")

    assert env.ok is False
    assert env.exit_code == ExitCode.INTERNAL_ERROR
    assert env.error is not None
    assert env.error.code == "ERR_INTERNAL"


def test_implicit_completion_without_end_step(
    tmp_path: Path, write_workflow: Callable[..., Path]
) -> None:
    """A workflow with only cli steps (no end step) completes implicitly."""
    wf = write_workflow("    - id: greet\n      kind: cli\n      command: echo done")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.status == "completed"
