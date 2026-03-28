from __future__ import annotations

from pathlib import Path

from checkpointflow.engine.queries import query_inspect, query_status
from checkpointflow.engine.runner import resume_workflow, run_workflow


def _write_cli_end_workflow(tmp_path: Path) -> Path:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: test_wf
  version: "1.0"
  inputs:
    type: object
  steps:
    - id: greet
      kind: cli
      command: echo hello
    - id: done
      kind: end
      result:
        msg: done
""")
    return wf


def _write_await_workflow(tmp_path: Path) -> Path:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: await_wf
  inputs:
    type: object
  steps:
    - id: wait
      kind: await_event
      audience: user
      event_name: input_needed
      prompt: Provide input
      input_schema:
        type: object
    - id: done
      kind: end
""")
    return wf


# --- Status ---


def test_status_completed_run(tmp_path: Path) -> None:
    wf = _write_cli_end_workflow(tmp_path)
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None
    status = query_status(env.run_id, base_dir=tmp_path / "store")
    assert status.ok is True
    assert status.status == "completed"
    assert status.exit_code == 0


def test_status_waiting_run(tmp_path: Path) -> None:
    wf = _write_await_workflow(tmp_path)
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None
    status = query_status(env.run_id, base_dir=tmp_path / "store")
    assert status.ok is True
    assert status.status == "waiting"
    assert status.exit_code == 40
    assert status.wait is not None
    assert status.wait.event_name == "input_needed"


def test_status_includes_workflow_metadata(tmp_path: Path) -> None:
    wf = _write_cli_end_workflow(tmp_path)
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None
    status = query_status(env.run_id, base_dir=tmp_path / "store")
    assert status.workflow_id == "test_wf"
    assert status.workflow_version == "1.0"


def test_status_run_not_found(tmp_path: Path) -> None:
    status = query_status("fake", base_dir=tmp_path / "store")
    assert status.ok is False
    assert status.error is not None
    assert status.error.code == "ERR_RUN_NOT_FOUND"


def test_status_completed_includes_result(tmp_path: Path) -> None:
    wf = _write_cli_end_workflow(tmp_path)
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None
    status = query_status(env.run_id, base_dir=tmp_path / "store")
    assert status.result == {"msg": "done"}


# --- Inspect ---


def test_inspect_completed_run(tmp_path: Path) -> None:
    wf = _write_cli_end_workflow(tmp_path)
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None
    insp = query_inspect(env.run_id, base_dir=tmp_path / "store")
    assert insp.ok is True
    assert insp.result is not None


def test_inspect_includes_step_results(tmp_path: Path) -> None:
    wf = _write_cli_end_workflow(tmp_path)
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None
    insp = query_inspect(env.run_id, base_dir=tmp_path / "store")
    steps = insp.result["step_results"]
    assert len(steps) == 2
    assert steps[0]["step_id"] == "greet"
    assert steps[1]["step_id"] == "done"


def test_inspect_includes_events(tmp_path: Path) -> None:
    wf = _write_await_workflow(tmp_path)
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None
    resume_workflow(env.run_id, "input_needed", '{"x":1}', base_dir=tmp_path / "store")
    insp = query_inspect(env.run_id, base_dir=tmp_path / "store")
    events = insp.result["events"]
    assert len(events) == 1
    assert events[0]["event_name"] == "input_needed"


def test_inspect_includes_inputs(tmp_path: Path) -> None:
    wf = _write_cli_end_workflow(tmp_path)
    env = run_workflow(wf, '{"key":"val"}', base_dir=tmp_path / "store")
    assert env.run_id is not None
    insp = query_inspect(env.run_id, base_dir=tmp_path / "store")
    assert insp.result["inputs"] == {"key": "val"}


def test_inspect_run_not_found(tmp_path: Path) -> None:
    insp = query_inspect("fake", base_dir=tmp_path / "store")
    assert insp.ok is False
    assert insp.error is not None
    assert insp.error.code == "ERR_RUN_NOT_FOUND"
