"""Tests for bulk delete from the GUI run list."""

from __future__ import annotations

from pathlib import Path

import pytest

from checkpointflow.persistence.store import Store


@pytest.fixture()
def store(tmp_path: Path) -> Store:
    return Store(base_dir=tmp_path)


def _make_completed_run(store: Store, workflow_id: str = "wf1") -> str:
    """Create a run in 'completed' status."""
    run_id = store.create_run(
        workflow_id=workflow_id,
        workflow_version="1.0",
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.update_run(run_id, status="completed", result_json='{"done":true}')
    store.insert_step_result(
        run_id=run_id, step_id="s1", step_kind="cli", execution_order=0, exit_code=0
    )
    d = store.run_dir(run_id)
    (d / "stdout" / "s1.txt").write_text("hello")
    return run_id


def _make_active_run(store: Store) -> str:
    """Create a run in 'waiting' status (cannot be deleted)."""
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.update_run(run_id, status="waiting")
    return run_id


# --- bulk_delete_runs API handler ---


def test_bulk_delete_runs_api_handler(store: Store) -> None:
    from checkpointflow.gui.api import bulk_delete_runs

    r1 = _make_completed_run(store)
    r2 = _make_completed_run(store)
    result = bulk_delete_runs(store, [r1, r2])
    assert len(result["deleted"]) == 2
    assert r1 in result["deleted"]
    assert r2 in result["deleted"]
    assert len(result["skipped"]) == 0
    assert store.get_run(r1) is None
    assert store.get_run(r2) is None


def test_bulk_delete_skips_active_runs(store: Store) -> None:
    from checkpointflow.gui.api import bulk_delete_runs

    completed = _make_completed_run(store)
    active = _make_active_run(store)
    result = bulk_delete_runs(store, [completed, active])
    assert completed in result["deleted"]
    assert active in result["skipped"]
    # Active run is still there
    assert store.get_run(active) is not None


def test_bulk_delete_empty_list(store: Store) -> None:
    from checkpointflow.gui.api import bulk_delete_runs

    result = bulk_delete_runs(store, [])
    assert result["deleted"] == []
    assert result["skipped"] == []


def test_bulk_delete_nonexistent_runs_skipped(store: Store) -> None:
    from checkpointflow.gui.api import bulk_delete_runs

    result = bulk_delete_runs(store, ["nonexistent1", "nonexistent2"])
    assert len(result["skipped"]) == 2


# --- HTTP endpoint ---


def test_bulk_delete_mixed_statuses(store: Store) -> None:
    """Integration test: mix of completed, failed, cancelled, and active runs."""
    from checkpointflow.gui.api import bulk_delete_runs

    completed = _make_completed_run(store)

    failed = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.update_run(failed, status="failed")

    cancelled = store.create_run(
        workflow_id="wf1",
        workflow_version=None,
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.update_run(cancelled, status="cancelled")

    active = _make_active_run(store)

    result = bulk_delete_runs(store, [completed, failed, cancelled, active])
    assert set(result["deleted"]) == {completed, failed, cancelled}
    assert result["skipped"] == [active]


def test_bulk_delete_result_shape(store: Store) -> None:
    """Verify the result dict always has both keys."""
    from checkpointflow.gui.api import bulk_delete_runs

    r1 = _make_completed_run(store)
    result = bulk_delete_runs(store, [r1, "nonexistent"])
    assert "deleted" in result
    assert "skipped" in result
    assert isinstance(result["deleted"], list)
    assert isinstance(result["skipped"], list)
    assert r1 in result["deleted"]
    assert "nonexistent" in result["skipped"]
