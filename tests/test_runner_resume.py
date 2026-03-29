from __future__ import annotations

from pathlib import Path

from checkpointflow.engine.runner import resume_workflow, run_workflow


def _write_await_workflow(tmp_path: Path, after_approve: str = "") -> Path:
    """Workflow: cli echo → await_event with transitions → apply/rejected."""
    wf = tmp_path / "workflow.yaml"
    extra_steps = (
        after_approve
        or """\
    - id: apply
      kind: cli
      command: echo applied
    - id: done
      kind: end
      result:
        status: approved"""
    )
    wf.write_text(f"""\
schema_version: checkpointflow/v1
workflow:
  id: test_wf
  version: "1.0"
  inputs:
    type: object
  steps:
    - id: plan
      kind: cli
      command: echo planning
    - id: approval
      kind: await_event
      audience: user
      event_name: change_approval
      prompt: Approve or reject
      input_schema:
        type: object
        required: [decision]
        properties:
          decision:
            type: string
            enum: [approve, reject]
      transitions:
        - when: ${{event.decision == "approve"}}
          next: apply
        - when: ${{event.decision == "reject"}}
          next: rejected
{extra_steps}
    - id: rejected
      kind: end
      result:
        status: rejected
""")
    return wf


def _write_simple_await_workflow(tmp_path: Path) -> Path:
    """Workflow: await_event (no transitions) → end."""
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: simple_wf
  inputs:
    type: object
  steps:
    - id: wait
      kind: await_event
      audience: user
      event_name: input_needed
      input_schema:
        type: object
    - id: done
      kind: end
""")
    return wf


def _run_to_waiting(tmp_path: Path, wf: Path) -> str:
    """Run a workflow and return the run_id from the waiting envelope."""
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.status == "waiting"
    assert env.run_id is not None
    return env.run_id


# --- Await event halting ---


def test_run_await_event_returns_waiting(tmp_path: Path) -> None:
    wf = _write_await_workflow(tmp_path)
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.status == "waiting"
    assert env.exit_code == 40


def test_run_await_event_has_wait_detail(tmp_path: Path) -> None:
    wf = _write_await_workflow(tmp_path)
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.wait is not None
    assert env.wait.event_name == "change_approval"
    assert env.wait.audience == "user"
    assert env.wait.kind == "external_event"


def test_run_await_event_has_resume_command(tmp_path: Path) -> None:
    wf = _write_await_workflow(tmp_path)
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.wait is not None
    assert "cpf resume" in env.wait.resume.command
    assert env.run_id is not None
    assert env.run_id in env.wait.resume.command


def test_run_await_event_has_run_id(tmp_path: Path) -> None:
    wf = _write_await_workflow(tmp_path)
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None
    assert len(env.run_id) > 0


# --- Resume validation ---


def test_resume_run_not_found(tmp_path: Path) -> None:
    env = resume_workflow("fake_id", "ev", "{}", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == "ERR_RUN_NOT_FOUND"


def test_resume_run_not_waiting(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: wf
  inputs:
    type: object
  steps:
    - id: done
      kind: end
""")
    env = run_workflow(wf, "{}", base_dir=tmp_path / "store")
    assert env.run_id is not None
    env2 = resume_workflow(env.run_id, "ev", "{}", base_dir=tmp_path / "store")
    assert env2.ok is False
    assert env2.error is not None
    assert env2.error.code == "ERR_RUN_NOT_WAITING"


def test_resume_event_name_mismatch(tmp_path: Path) -> None:
    wf = _write_simple_await_workflow(tmp_path)
    run_id = _run_to_waiting(tmp_path, wf)
    env = resume_workflow(run_id, "wrong_event", "{}", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == "ERR_RESUME_EVENT_MISMATCH"


def test_resume_event_schema_fail(tmp_path: Path) -> None:
    wf = _write_await_workflow(tmp_path)
    run_id = _run_to_waiting(tmp_path, wf)
    # Schema requires "decision" with enum values
    env = resume_workflow(
        run_id, "change_approval", '{"decision":"maybe"}', base_dir=tmp_path / "store"
    )
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == "ERR_VALIDATION_EVENT_INPUT"


def test_resume_invalid_json(tmp_path: Path) -> None:
    wf = _write_simple_await_workflow(tmp_path)
    run_id = _run_to_waiting(tmp_path, wf)
    env = resume_workflow(run_id, "input_needed", "{bad", base_dir=tmp_path / "store")
    assert env.ok is False
    assert env.error is not None
    assert env.error.code == "ERR_VALIDATION_EVENT_INPUT"


# --- Resume execution ---


def test_resume_continues_to_end(tmp_path: Path) -> None:
    wf = _write_simple_await_workflow(tmp_path)
    run_id = _run_to_waiting(tmp_path, wf)
    env = resume_workflow(run_id, "input_needed", "{}", base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.status == "completed"
    assert env.exit_code == 0


def test_resume_with_transitions_approve(tmp_path: Path) -> None:
    wf = _write_await_workflow(tmp_path)
    run_id = _run_to_waiting(tmp_path, wf)
    env = resume_workflow(
        run_id,
        "change_approval",
        '{"decision":"approve"}',
        base_dir=tmp_path / "store",
    )
    assert env.ok is True
    assert env.status == "completed"


def test_resume_with_transitions_reject(tmp_path: Path) -> None:
    wf = _write_await_workflow(tmp_path)
    run_id = _run_to_waiting(tmp_path, wf)
    env = resume_workflow(
        run_id,
        "change_approval",
        '{"decision":"reject"}',
        base_dir=tmp_path / "store",
    )
    assert env.ok is True
    assert env.status == "completed"
    assert env.result is not None
    assert env.result["status"] == "rejected"


def test_resume_no_transition_match_falls_through(tmp_path: Path) -> None:
    """When no transition matches, fall through to the next step in the array."""
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
        properties:
          x:
            type: string
      transitions:
        - when: ${event.x == "a"}
          next: done
    - id: fallthrough
      kind: cli
      command: echo fell through
    - id: done
      kind: end
""")
    run_id = _run_to_waiting(tmp_path, wf)
    env = resume_workflow(run_id, "ev", '{"x":"b"}', base_dir=tmp_path / "store")
    assert env.ok is True
    assert env.status == "completed"


def test_run_waiting_envelope_has_workflow_name(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: named_wf
  name: Named Workflow
  description: A workflow with metadata
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
    assert env.ok is True
    assert env.status == "waiting"
    assert env.workflow_name == "Named Workflow"
    assert env.workflow_description == "A workflow with metadata"


def test_resume_envelope_has_workflow_name(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: named_wf
  name: Named Workflow
  description: A workflow with metadata
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
    env2 = resume_workflow(env.run_id, "ev", "{}", base_dir=tmp_path / "store")
    assert env2.ok is True
    assert env2.workflow_name == "Named Workflow"
    assert env2.workflow_description == "A workflow with metadata"


def test_resume_persists_event(tmp_path: Path) -> None:
    from checkpointflow.persistence.store import Store

    wf = _write_simple_await_workflow(tmp_path)
    run_id = _run_to_waiting(tmp_path, wf)
    resume_workflow(run_id, "input_needed", '{"val":1}', base_dir=tmp_path / "store")
    store = Store(base_dir=tmp_path / "store")
    events = store.get_events(run_id)
    assert len(events) == 1
    assert events[0]["event_name"] == "input_needed"
