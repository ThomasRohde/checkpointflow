"""Tests for security and correctness fixes from code review."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from checkpointflow.engine.runner import resume_workflow, run_workflow
from checkpointflow.models.errors import ErrorCode

# --- P1: Resume rejects modified workflow ---


def test_resume_rejects_modified_workflow(tmp_path: Path) -> None:
    """A run paused against workflow v1 must not resume against v2."""
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: test_wf
  inputs:
    type: object
  steps:
    - id: wait
      kind: await_event
      audience: user
      event_name: input
      input_schema:
        type: object
    - id: done
      kind: end
      result:
        status: original
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path)
    assert env.status == "waiting"
    run_id = env.run_id

    # Modify the workflow file
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: test_wf
  inputs:
    type: object
  steps:
    - id: wait
      kind: await_event
      audience: user
      event_name: input
      input_schema:
        type: object
    - id: done
      kind: end
      result:
        status: mutated
""")

    env2 = resume_workflow(run_id, "input", "{}", base_dir=tmp_path)  # type: ignore[arg-type]
    assert env2.ok is False
    assert env2.error is not None
    assert env2.error.code == ErrorCode.ERR_VALIDATION_WORKFLOW
    assert "changed" in env2.error.message.lower()


def test_resume_succeeds_with_unchanged_workflow(tmp_path: Path) -> None:
    """Resume works when the workflow file has not been modified."""
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: test_wf
  inputs:
    type: object
  steps:
    - id: wait
      kind: await_event
      audience: user
      event_name: input
      input_schema:
        type: object
    - id: done
      kind: end
      result:
        status: original
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path)
    assert env.status == "waiting"
    run_id = env.run_id

    env2 = resume_workflow(run_id, "input", "{}", base_dir=tmp_path)  # type: ignore[arg-type]
    assert env2.ok is True
    assert env2.result is not None
    assert env2.result["status"] == "original"


# --- P1: Broken if-conditions fail the run ---


def test_broken_if_condition_fails_run(tmp_path: Path, write_workflow: Callable[..., Path]) -> None:
    """A step with an unresolvable if-condition must fail the run."""
    wf = write_workflow(
        """\
    - id: guarded
      kind: cli
      if: steps.missing.outputs.ok == "yes"
      command: echo should-not-run
    - id: done
      kind: end""",
    )
    env = run_workflow(wf, "{}", base_dir=tmp_path)
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == ErrorCode.ERR_STEP_FAILED
    assert "if-condition" in env.error.message.lower() or "invalid" in env.error.message.lower()


def test_valid_false_if_condition_skips_step(
    tmp_path: Path, write_workflow: Callable[..., Path]
) -> None:
    """A valid if-condition that evaluates to false should skip the step."""
    wf = write_workflow(
        """\
    - id: guarded
      kind: cli
      if: inputs.mode == "full"
      command: echo should-skip
    - id: done
      kind: end
      result:
        status: completed""",
        inputs_schema="""\
type: object
    properties:
      mode:
        type: string""",
    )
    env = run_workflow(wf, json.dumps({"mode": "lite"}), base_dir=tmp_path)
    assert env.ok is True


# --- P2: Duplicate step IDs rejected at runtime ---


def test_run_rejects_duplicate_step_ids(tmp_path: Path) -> None:
    """cpf run must reject workflows with duplicate step IDs."""
    wf = tmp_path / "workflow.yaml"
    # Write directly to bypass schema validation which may also catch this
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: test_wf
  inputs:
    type: object
  steps:
    - id: one
      kind: cli
      command: echo first
    - id: one
      kind: cli
      command: echo second
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path)
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == ErrorCode.ERR_DUPLICATE_STEP_ID
