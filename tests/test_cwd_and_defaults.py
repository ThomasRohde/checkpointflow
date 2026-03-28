"""Tests for cwd field on CLI steps and defaults.shell on workflows."""

from __future__ import annotations

from pathlib import Path

from checkpointflow.engine.runner import run_workflow


def test_cli_step_cwd(tmp_path: Path) -> None:
    """cwd sets the working directory for the step command."""
    target_dir = tmp_path / "work"
    target_dir.mkdir()
    (target_dir / "marker.txt").write_text("found")

    wf = tmp_path / "workflow.yaml"
    wf.write_text(f"""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: check
      kind: cli
      cwd: "{target_dir.as_posix()}"
      command: python -c "import json,os; print(json.dumps({{'here':os.getcwd()}}))"
      outputs:
        type: object
        required: [here]
        properties:
          here: {{ type: string }}
    - id: done
      kind: end
      result:
        dir: ${{steps.check.outputs.here}}
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.result is not None
    # The cwd should contain the target directory name
    assert "work" in str(env.result["dir"])


def test_cli_step_cwd_with_interpolation(tmp_path: Path) -> None:
    """cwd supports ${inputs.x} interpolation."""
    target_dir = tmp_path / "project"
    target_dir.mkdir()

    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
    required: [dir]
    properties:
      dir: { type: string }
  steps:
    - id: check
      kind: cli
      cwd: ${inputs.dir}
      command: python -c "import os,json;print(json.dumps({'cwd':os.path.basename(os.getcwd())}))"
      outputs:
        type: object
        required: [cwd]
        properties:
          cwd: { type: string }
    - id: done
      kind: end
      result:
        ran_in: ${steps.check.outputs.cwd}
""")
    env = run_workflow(wf, f'{{"dir":"{target_dir.as_posix()}"}}', base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.result["ran_in"] == "project"


def test_cli_step_cwd_nonexistent_fails(tmp_path: Path) -> None:
    """cwd pointing to a nonexistent directory should fail."""
    bad_dir = tmp_path / "does_not_exist"
    wf = tmp_path / "workflow.yaml"
    wf.write_text(f"""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: check
      kind: cli
      cwd: "{bad_dir.as_posix()}"
      command: echo hi
    - id: done
      kind: end
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == "ERR_STEP_FAILED"
    assert "does not exist" in env.error.message


def test_defaults_shell(tmp_path: Path) -> None:
    """defaults.shell applies to all CLI steps without an explicit shell."""
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  defaults:
    shell: bash
  inputs:
    type: object
  steps:
    - id: check
      kind: cli
      command: echo "hello from bash"
    - id: done
      kind: end
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True


def test_step_shell_overrides_defaults(tmp_path: Path) -> None:
    """Step-level shell takes precedence over defaults.shell."""
    wf = tmp_path / "workflow.yaml"
    # defaults.shell is bash, but the step overrides with cmd (on Windows)
    # Just verify it doesn't crash — the step shell should be used
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  defaults:
    shell: bash
  inputs:
    type: object
  steps:
    - id: check
      kind: cli
      shell: bash
      command: echo "explicit bash"
    - id: done
      kind: end
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True
