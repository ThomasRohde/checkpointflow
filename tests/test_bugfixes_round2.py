"""Tests for blackbox round 2 bug fixes."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from checkpointflow.cli import app
from checkpointflow.engine.queries import query_status
from checkpointflow.engine.runner import run_workflow
from checkpointflow.engine.steps.end_step import execute as end_execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import EndStep

runner = CliRunner()


# --- Bug 1: Expression interpolation in end step result ---


def test_end_step_interpolates_inputs(tmp_path: Path) -> None:
    step = EndStep.model_validate(
        {
            "id": "done",
            "kind": "end",
            "result": {"greeting": "${inputs.name}"},
        }
    )
    ctx = RunContext(
        run_id="test",
        inputs={"name": "Alice"},
        step_outputs={},
        run_dir=tmp_path,
    )
    result = end_execute(step, ctx)
    assert result.outputs == {"greeting": "Alice"}


def test_end_step_interpolates_step_outputs(tmp_path: Path) -> None:
    step = EndStep.model_validate(
        {
            "id": "done",
            "kind": "end",
            "result": {"url": "${steps.apply.outputs.page_url}"},
        }
    )
    ctx = RunContext(
        run_id="test",
        inputs={},
        step_outputs={"apply": {"page_url": "https://example.com"}},
        run_dir=tmp_path,
    )
    result = end_execute(step, ctx)
    assert result.outputs == {"url": "https://example.com"}


def test_end_step_interpolation_in_full_workflow(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
    required: [name]
    properties:
      name: { type: string }
  steps:
    - id: done
      kind: end
      result:
        greeting: "Hello, ${inputs.name}!"
""")
    env = run_workflow(wf, '{"name":"World"}', base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.result is not None
    assert env.result["greeting"] == "Hello, World!"


# --- Bug 2: Unicode on Windows ---


def test_cli_step_unicode_output(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: greet
      kind: cli
      command: python -c "print('caf\\u00e9')"
    - id: done
      kind: end
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.exit_code != 90  # Must not be ERR_INTERNAL


# --- Bug 3: Missing optional input gives clear error ---


def test_missing_input_variable_gives_step_error(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: greet
      kind: cli
      command: echo ${inputs.missing_field}
    - id: done
      kind: end
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.exit_code == 30  # STEP_FAILED, not 90 (INTERNAL_ERROR)
    assert env.error is not None
    assert env.error.code == "ERR_STEP_FAILED"


def test_init_template_runs_with_input(tmp_path: Path) -> None:
    out = tmp_path / "wf.yaml"
    runner.invoke(app, ["init", "--file", str(out)])
    result = runner.invoke(
        app,
        ["run", "-f", str(out), "--input", '{"name":"World"}'],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code == 0


def test_init_template_rejects_empty_input(tmp_path: Path) -> None:
    out = tmp_path / "wf.yaml"
    runner.invoke(app, ["init", "--file", str(out)])
    result = runner.invoke(
        app,
        ["run", "-f", str(out), "--input", "{}"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code == 10  # Validation error, not 90


# --- Bug 5: Status includes prompt/instructions ---


def test_status_waiting_includes_prompt(tmp_path: Path) -> None:
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
      event_name: approval
      prompt: Please approve this change.
      input_schema:
        type: object
    - id: done
      kind: end
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None

    status = query_status(env.run_id, base_dir=tmp_path / "store")
    assert status.wait is not None
    assert status.wait.prompt == "Please approve this change."
    assert status.wait.instructions is not None
    assert len(status.wait.instructions) > 0
    assert status.wait.audience == "user"
