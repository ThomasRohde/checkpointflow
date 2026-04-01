"""HTTP-level integration tests for the GUI server."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from checkpointflow.gui.server import create_app
from checkpointflow.persistence.store import Store


@pytest.fixture()
def base_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def store(base_dir: Path) -> Store:
    return Store(base_dir=base_dir)


@pytest.fixture()
def client(base_dir: Path) -> TestClient:
    app = create_app(base_dir=base_dir)
    return TestClient(app)


def _make_completed_run(store: Store) -> str:
    run_id = store.create_run(
        workflow_id="wf1",
        workflow_version="1.0",
        workflow_hash="abc",
        workflow_path="/tmp/wf.yaml",
        inputs_json="{}",
    )
    store.update_run(run_id, status="completed", result_json='{"done": true}')
    return run_id


# --- /api/runs ---


def test_api_runs_empty(client: TestClient) -> None:
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_api_runs_returns_list(client: TestClient, store: Store) -> None:
    _make_completed_run(store)
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1


# --- /api/runs/{run_id} ---


def test_api_run_detail_found(client: TestClient, store: Store) -> None:
    run_id = _make_completed_run(store)
    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["run_id"] == run_id


def test_api_run_detail_not_found(client: TestClient) -> None:
    resp = client.get("/api/runs/nonexistent")
    assert resp.status_code == 404


# --- DELETE /api/runs/{run_id} ---


def test_api_delete_run(client: TestClient, store: Store) -> None:
    run_id = _make_completed_run(store)
    resp = client.delete(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_api_delete_run_not_found(client: TestClient) -> None:
    resp = client.delete("/api/runs/nonexistent")
    assert resp.status_code == 404


# --- POST /api/runs/bulk-delete ---


def test_api_bulk_delete(client: TestClient, store: Store) -> None:
    r1 = _make_completed_run(store)
    r2 = _make_completed_run(store)
    resp = client.post("/api/runs/bulk-delete", json={"run_ids": [r1, r2]})
    assert resp.status_code == 200
    assert len(resp.json()["deleted"]) == 2


# --- /api/runs/{run_id}/steps/{step_id}/{stream} ---


def test_api_step_stream_invalid(client: TestClient) -> None:
    resp = client.get("/api/runs/x/steps/y/invalid")
    assert resp.status_code == 400


def test_api_step_stream_path_traversal_run_id(client: TestClient, store: Store) -> None:
    """Verify _safe_path_component rejects '..' in run_id."""
    from checkpointflow.gui.api import get_step_output

    result = get_step_output(store, "../etc", "s1", "stdout")
    assert result is None


def test_api_step_stream_path_traversal_step_id(client: TestClient, store: Store) -> None:
    """Verify _safe_path_component rejects '..' in step_id."""
    from checkpointflow.gui.api import get_step_output

    result = get_step_output(store, "valid_id", "../etc/passwd", "stdout")
    assert result is None


def test_api_step_stream_stdout_success(client: TestClient, store: Store, base_dir: Path) -> None:
    run_id = _make_completed_run(store)
    # Write a fake stdout file
    stdout_dir = base_dir / "runs" / run_id / "stdout"
    stdout_dir.mkdir(parents=True, exist_ok=True)
    (stdout_dir / "step1.txt").write_text("hello world", encoding="utf-8")
    resp = client.get(f"/api/runs/{run_id}/steps/step1/stdout")
    assert resp.status_code == 200
    assert resp.text == "hello world"


# --- /api/workflows ---


def test_api_workflows_list(client: TestClient) -> None:
    resp = client.get("/api/workflows")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# --- Security headers ---


def test_security_headers_present(client: TestClient) -> None:
    resp = client.get("/api/runs")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert "default-src" in resp.headers["content-security-policy"]


# --- SPA fallback ---


def test_spa_fallback(client: TestClient) -> None:
    resp = client.get("/some/random/path")
    assert resp.status_code in (200, 503)


# --- CORS ---


def test_cors_preflight_returns_headers(base_dir: Path) -> None:
    app = create_app(base_dir=base_dir)
    client = TestClient(app)
    resp = client.options(
        "/api/runs",
        headers={"Origin": "http://localhost:8420", "Access-Control-Request-Method": "GET"},
    )
    assert resp.status_code == 204
    assert resp.headers["access-control-allow-origin"] == "http://localhost:8420"


def test_cors_rejects_non_localhost_origin(base_dir: Path) -> None:
    app = create_app(base_dir=base_dir)
    client = TestClient(app)
    resp = client.get("/api/runs", headers={"Origin": "http://evil.com"})
    assert "access-control-allow-origin" not in resp.headers


def test_cors_rejects_localhost_prefix_bypass(base_dir: Path) -> None:
    app = create_app(base_dir=base_dir)
    client = TestClient(app)
    resp = client.get("/api/runs", headers={"Origin": "http://localhost.evil.com"})
    assert "access-control-allow-origin" not in resp.headers
