from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from checkpointflow.persistence.store import PersistenceError, Store


@pytest.fixture()
def store(tmp_path: Path) -> Store:
    return Store(base_dir=tmp_path)


# --- DB initialization ---


def test_store_creates_db_file(tmp_path: Path) -> None:
    Store(base_dir=tmp_path)
    assert (tmp_path / "runs.db").exists()


def test_store_creates_tables(store: Store) -> None:
    cursor = store._conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cursor.fetchall()}
    assert {"runs", "events", "step_results"} <= tables


def test_store_idempotent_init(tmp_path: Path) -> None:
    Store(base_dir=tmp_path)
    Store(base_dir=tmp_path)  # should not raise


# --- context manager ---


def test_store_context_manager_returns_self(tmp_path: Path) -> None:
    with Store(base_dir=tmp_path) as store:
        assert isinstance(store, Store)


def test_store_context_manager_closes_on_exit(tmp_path: Path) -> None:
    with Store(base_dir=tmp_path) as store:
        store.create_run(
            workflow_id="wf1",
            workflow_version="1.0",
            workflow_hash="abc",
            workflow_path="/tmp/wf.yaml",
            inputs_json="{}",
        )
    # Connection should be closed — operations should raise
    with pytest.raises(Exception):  # noqa: B017
        store._conn.execute("SELECT 1")


def test_store_context_manager_closes_on_exception(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError), Store(base_dir=tmp_path) as store:
        raise RuntimeError("test")
    with pytest.raises(Exception):  # noqa: B017
        store._conn.execute("SELECT 1")


# --- list_runs ---


def _make_run(store: Store) -> str:
    return store.create_run(
        workflow_id="wf1",
        workflow_version="1.0",
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )


def test_list_runs_empty(store: Store) -> None:
    assert store.list_runs() == []


def test_list_runs_returns_all(store: Store) -> None:
    _make_run(store)
    _make_run(store)
    assert len(store.list_runs()) == 2


def test_list_runs_ordered_desc(store: Store) -> None:
    r1 = _make_run(store)
    time.sleep(0.02)
    r2 = _make_run(store)
    runs = store.list_runs()
    assert runs[0]["run_id"] == r2
    assert runs[1]["run_id"] == r1


def test_list_runs_contains_expected_fields(store: Store) -> None:
    _make_run(store)
    run = store.list_runs()[0]
    for field in (
        "run_id",
        "workflow_id",
        "workflow_version",
        "workflow_path",
        "status",
        "current_step_id",
        "created_at",
        "updated_at",
    ):
        assert field in run


# --- Run CRUD ---


def test_create_run_returns_id(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version="1.0",
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    assert isinstance(run_id, str)
    assert len(run_id) > 0


def test_create_run_sets_status_created(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    record = store.get_run(run_id)
    assert record is not None
    assert record["status"] == "created"


def test_create_run_stores_workflow_id(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="my_workflow",
        workflow_version="2.0",
        workflow_hash="def",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    record = store.get_run(run_id)
    assert record is not None
    assert record["workflow_id"] == "my_workflow"
    assert record["workflow_version"] == "2.0"


def test_create_run_stores_inputs_json(store: Store) -> None:
    inputs = json.dumps({"name": "Alice"})
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json=inputs,
    )
    record = store.get_run(run_id)
    assert record is not None
    assert json.loads(record["inputs_json"]) == {"name": "Alice"}


def test_get_run_nonexistent_returns_none(store: Store) -> None:
    assert store.get_run("nonexistent") is None


def test_update_run_status(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.update_run(run_id, status="running", current_step_id="step1")
    record = store.get_run(run_id)
    assert record is not None
    assert record["status"] == "running"
    assert record["current_step_id"] == "step1"


def test_update_run_step_outputs(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    outputs = json.dumps({"step1": {"key": "val"}})
    store.update_run(run_id, step_outputs_json=outputs)
    record = store.get_run(run_id)
    assert record is not None
    assert json.loads(record["step_outputs_json"]) == {"step1": {"key": "val"}}


def test_update_run_result_json(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.update_run(run_id, status="completed", result_json=json.dumps({"done": True}))
    record = store.get_run(run_id)
    assert record is not None
    assert json.loads(record["result_json"]) == {"done": True}


def test_update_run_nonexistent_raises(store: Store) -> None:
    with pytest.raises(PersistenceError):
        store.update_run("fake_id", status="running")


def test_update_run_rejects_invalid_column(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    with pytest.raises(PersistenceError, match="Invalid column"):
        store.update_run(run_id, bogus_column="bad")


def test_close_is_idempotent(tmp_path: Path) -> None:
    store = Store(base_dir=tmp_path)
    store.close()
    store.close()  # should not raise


# --- Step results ---


def test_insert_step_result(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.insert_step_result(
        run_id=run_id,
        step_id="step1",
        step_kind="cli",
        execution_order=0,
        exit_code=0,
    )
    results = store.get_step_results(run_id)
    assert len(results) == 1
    assert results[0]["step_id"] == "step1"
    assert results[0]["exit_code"] == 0


def test_step_result_execution_order(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.insert_step_result(run_id=run_id, step_id="s1", step_kind="cli", execution_order=0)
    store.insert_step_result(run_id=run_id, step_id="s2", step_kind="cli", execution_order=1)
    results = store.get_step_results(run_id)
    assert len(results) == 2
    assert results[0]["step_id"] == "s1"
    assert results[1]["step_id"] == "s2"


# --- Run directory ---


def test_run_dir_creates_subdirs(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    d = store.run_dir(run_id)
    assert (d / "stdout").is_dir()
    assert (d / "stderr").is_dir()
    assert (d / "artifacts").is_dir()


def test_run_dir_idempotent(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    d1 = store.run_dir(run_id)
    d2 = store.run_dir(run_id)
    assert d1 == d2


# --- Timestamps ---


def test_created_at_is_set(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    record = store.get_run(run_id)
    assert record is not None
    assert record["created_at"] is not None


def test_updated_at_changes_on_update(store: Store) -> None:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    record1 = store.get_run(run_id)
    assert record1 is not None
    time.sleep(0.01)
    store.update_run(run_id, status="running")
    record2 = store.get_run(run_id)
    assert record2 is not None
    assert record2["updated_at"] >= record1["updated_at"]


# --- Events ---


def _make_run(store: Store) -> str:
    return store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )


def test_insert_event_returns_event_id(store: Store) -> None:
    run_id = _make_run(store)
    event_id = store.insert_event(run_id=run_id, event_name="approval", event_json='{"ok":true}')
    assert isinstance(event_id, str)
    assert len(event_id) > 0


def test_insert_event_stores_data(store: Store) -> None:
    run_id = _make_run(store)
    store.insert_event(run_id=run_id, event_name="approval", event_json='{"decision":"approve"}')
    events = store.get_events(run_id)
    assert len(events) == 1
    assert events[0]["event_name"] == "approval"
    assert events[0]["event_json"] == '{"decision":"approve"}'


def test_get_events_empty(store: Store) -> None:
    run_id = _make_run(store)
    assert store.get_events(run_id) == []


def test_get_events_ordered(store: Store) -> None:
    run_id = _make_run(store)
    store.insert_event(run_id=run_id, event_name="e1", event_json="{}")
    store.insert_event(run_id=run_id, event_name="e2", event_json="{}")
    events = store.get_events(run_id)
    assert len(events) == 2
    assert events[0]["event_name"] == "e1"
    assert events[1]["event_name"] == "e2"


def test_get_events_scoped_to_run(store: Store) -> None:
    r1 = _make_run(store)
    r2 = _make_run(store)
    store.insert_event(run_id=r1, event_name="e_r1", event_json="{}")
    store.insert_event(run_id=r2, event_name="e_r2", event_json="{}")
    assert len(store.get_events(r1)) == 1
    assert store.get_events(r1)[0]["event_name"] == "e_r1"
