from __future__ import annotations

import json
from pathlib import Path

from checkpointflow.engine.runner import run_workflow


def _write_workflow(tmp_path: Path, steps_yaml: str, inputs_schema: str = "type: object") -> Path:
    wf = tmp_path / "workflow.yaml"
    wf.write_text(f"""\
schema_version: checkpointflow/v1
workflow:
  id: test_wf
  version: "1.0"
  inputs:
    {inputs_schema}
  steps:
{steps_yaml}
""")
    return wf


def _write_input(tmp_path: Path, data: dict[str, object]) -> Path:
    p = tmp_path / "input.json"
    p.write_text(json.dumps(data))
    return p


# --- Input parsing ---


def test_run_inline_input(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True


def test_run_file_input(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
        """\
    - id: done
      kind: end""",
    )
    inp = _write_input(tmp_path, {})
    env = run_workflow(wf, f"@{inp}", base_dir=tmp_path / "store")
    assert env.ok is True


def test_run_invalid_json_input(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{bad", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == "ERR_VALIDATION_INPUT"


def test_run_input_file_not_found(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "@nope.json", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == "ERR_FILE_NOT_FOUND"


def test_run_input_schema_validation(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
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


def test_run_single_end_step(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.status == "completed"
    assert env.exit_code == 0


def test_run_cli_then_end(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
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


def test_run_step_outputs_forwarded(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
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


def test_run_skip_step_with_false_if(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
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


def test_run_step_with_true_if(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
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


def test_run_cli_failure_stops(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
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


def test_run_unsupported_step(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
        """\
    - id: call_api
      kind: api
      method: GET
      url: https://example.com
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.exit_code == 80


# --- Persistence ---


def test_run_envelope_has_run_id(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None
    assert len(env.run_id) > 0


def test_run_envelope_has_workflow_id(tmp_path: Path) -> None:
    wf = _write_workflow(
        tmp_path,
        """\
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.workflow_id == "test_wf"
    assert env.workflow_version == "1.0"
