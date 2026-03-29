from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from checkpointflow.cli import app
from checkpointflow.persistence.store import PersistenceError, Store

runner = CliRunner()


@pytest.fixture()
def store(tmp_path: Path) -> Store:
    return Store(base_dir=tmp_path)


def _make_completed_run(store: Store) -> str:
    """Create a run in 'completed' status with child rows and a run directory."""
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version="1.0",
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.update_run(run_id, status="completed", result_json='{"done":true}')
    store.insert_step_result(
        run_id=run_id, step_id="s1", step_kind="cli", execution_order=0, exit_code=0
    )
    store.insert_event(run_id=run_id, event_name="approval", event_json='{"ok":true}')
    # Create run directory with some files
    d = store.run_dir(run_id)
    (d / "stdout" / "s1.txt").write_text("hello")
    return run_id


# --- Store.delete_run ---


def test_delete_run_removes_from_db(store: Store) -> None:
    run_id = _make_completed_run(store)
    store.delete_run(run_id)
    assert store.get_run(run_id) is None
    assert store.get_step_results(run_id) == []
    assert store.get_events(run_id) == []


def test_delete_run_removes_run_directory(store: Store) -> None:
    run_id = _make_completed_run(store)
    d = store.run_dir(run_id)
    assert d.exists()
    store.delete_run(run_id)
    assert not d.exists()


def test_delete_nonexistent_run_raises(store: Store) -> None:
    with pytest.raises(PersistenceError, match="not found"):
        store.delete_run("nonexistent")


def test_delete_active_run_raises(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.update_run(run_id, status="waiting")
    with pytest.raises(PersistenceError, match="Cannot delete"):
        store.delete_run(run_id)


def test_delete_cancelled_run_succeeds(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.update_run(run_id, status="cancelled")
    store.delete_run(run_id)
    assert store.get_run(run_id) is None


def test_delete_failed_run_succeeds(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.update_run(run_id, status="failed")
    store.delete_run(run_id)
    assert store.get_run(run_id) is None


# --- GUI API handler: delete_run ---


def test_api_handler_delete_run(store: Store) -> None:
    from checkpointflow.gui.api import delete_run

    run_id = _make_completed_run(store)
    result = delete_run(store, run_id)
    assert result is not None
    assert result["deleted"] is True
    assert store.get_run(run_id) is None


def test_api_handler_delete_nonexistent(store: Store) -> None:
    from checkpointflow.gui.api import delete_run

    result = delete_run(store, "nonexistent")
    assert result is None


def test_api_handler_delete_active_raises(store: Store) -> None:
    from checkpointflow.gui.api import delete_run

    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.update_run(run_id, status="waiting")
    with pytest.raises(PersistenceError, match="Cannot delete"):
        delete_run(store, run_id)


# --- CLI: cpf delete ---


def _cli_completed_run(tmp_path: Path) -> str:
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
    store_dir = str(tmp_path / "store")
    result = runner.invoke(
        app, ["run", "-f", str(wf), "--input", "{}"], env={"CHECKPOINTFLOW_BASE_DIR": store_dir}
    )
    return json.loads(result.stdout)["run_id"]


def test_cli_delete(tmp_path: Path) -> None:
    run_id = _cli_completed_run(tmp_path)
    result = runner.invoke(
        app,
        ["delete", "--run-id", run_id],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    assert result.exit_code == 0
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["status"] == "completed"


def test_cli_delete_nonexistent(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["delete", "--run-id", "fake"],
        env={"CHECKPOINTFLOW_BASE_DIR": str(tmp_path / "store")},
    )
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "ERR_RUN_NOT_FOUND"


def test_cli_delete_active_run_fails(tmp_path: Path) -> None:
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
    store_dir = str(tmp_path / "store")
    run_result = runner.invoke(
        app, ["run", "-f", str(wf), "--input", "{}"], env={"CHECKPOINTFLOW_BASE_DIR": store_dir}
    )
    run_id = json.loads(run_result.stdout)["run_id"]
    result = runner.invoke(
        app,
        ["delete", "--run-id", run_id],
        env={"CHECKPOINTFLOW_BASE_DIR": store_dir},
    )
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False
