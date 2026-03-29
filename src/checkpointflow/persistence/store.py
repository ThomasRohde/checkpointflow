from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class PersistenceError(Exception):
    pass


_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    workflow_name TEXT,
    workflow_description TEXT,
    workflow_version TEXT,
    workflow_hash TEXT NOT NULL,
    workflow_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    current_step_id TEXT,
    expected_event_name TEXT,
    expected_event_schema TEXT,
    inputs_json TEXT NOT NULL,
    step_outputs_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    event_name TEXT NOT NULL,
    event_json TEXT NOT NULL,
    validated INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS step_results (
    result_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    step_id TEXT NOT NULL,
    step_kind TEXT NOT NULL,
    exit_code INTEGER,
    stdout_path TEXT,
    stderr_path TEXT,
    outputs_json TEXT,
    error_code TEXT,
    error_message TEXT,
    execution_order INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    artifact_path TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    source_step_id TEXT,
    size_bytes INTEGER,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id, created_at);
CREATE INDEX IF NOT EXISTS idx_step_results_run_id ON step_results(run_id, execution_order);
CREATE INDEX IF NOT EXISTS idx_artifacts_run_id ON artifacts(run_id, source_step_id);
"""


class Store:
    """Manages SQLite database and artifact storage for workflow runs."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path.home() / ".checkpointflow"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.base_dir / "runs.db"
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_db()

    def _init_db(self) -> None:
        self._conn.executescript(_SCHEMA_SQL)
        self._migrate()

    def _migrate(self) -> None:
        """Add columns that may be missing from older databases."""
        cursor = self._conn.execute("PRAGMA table_info(runs)")
        existing = {row[1] for row in cursor.fetchall()}
        for col in ("workflow_name", "workflow_description"):
            if col not in existing:
                self._conn.execute(f"ALTER TABLE runs ADD COLUMN {col} TEXT")
        self._conn.commit()

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def create_run(
        self,
        *,
        workflow_id: str,
        workflow_name: str | None = None,
        workflow_description: str | None = None,
        workflow_version: str | None,
        workflow_hash: str,
        workflow_path: str,
        inputs_json: str,
    ) -> str:
        run_id = uuid.uuid4().hex
        now = self._now()
        self._conn.execute(
            """INSERT INTO runs
               (run_id, workflow_id, workflow_name, workflow_description,
                workflow_version, workflow_hash,
                workflow_path, inputs_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                workflow_id,
                workflow_name,
                workflow_description,
                workflow_version,
                workflow_hash,
                workflow_path,
                inputs_json,
                now,
                now,
            ),
        )
        self._conn.commit()
        return run_id

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        cursor = self._conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def update_run(self, run_id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        # Verify run exists
        if self.get_run(run_id) is None:
            msg = f"Run not found: {run_id}"
            raise PersistenceError(msg)

        kwargs["updated_at"] = self._now()
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = [*kwargs.values(), run_id]
        self._conn.execute(
            f"UPDATE runs SET {set_clause} WHERE run_id = ?",
            values,
        )
        self._conn.commit()

    def insert_step_result(
        self,
        *,
        run_id: str,
        step_id: str,
        step_kind: str,
        execution_order: int,
        exit_code: int | None = None,
        stdout_path: str | None = None,
        stderr_path: str | None = None,
        outputs_json: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        result_id = uuid.uuid4().hex
        self._conn.execute(
            """INSERT INTO step_results
               (result_id, run_id, step_id, step_kind, exit_code,
                stdout_path, stderr_path, outputs_json,
                error_code, error_message, execution_order, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result_id,
                run_id,
                step_id,
                step_kind,
                exit_code,
                stdout_path,
                stderr_path,
                outputs_json,
                error_code,
                error_message,
                execution_order,
                self._now(),
            ),
        )
        self._conn.commit()

    def get_step_results(self, run_id: str) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            "SELECT * FROM step_results WHERE run_id = ? ORDER BY execution_order",
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def insert_event(
        self,
        *,
        run_id: str,
        event_name: str,
        event_json: str,
    ) -> str:
        event_id = uuid.uuid4().hex
        self._conn.execute(
            """INSERT INTO events
               (event_id, run_id, event_name, event_json, validated, created_at)
               VALUES (?, ?, ?, ?, 1, ?)""",
            (event_id, run_id, event_name, event_json, self._now()),
        )
        self._conn.commit()
        return event_id

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            "SELECT * FROM events WHERE run_id = ? ORDER BY created_at",
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def run_dir(self, run_id: str) -> Path:
        d = self.base_dir / "runs" / run_id
        for sub in ("stdout", "stderr", "artifacts"):
            (d / sub).mkdir(parents=True, exist_ok=True)
        return d

    def close(self) -> None:
        self._conn.close()
