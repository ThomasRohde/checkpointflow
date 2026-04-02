"""Shared serialization helpers for step results, events, and workflow metadata."""

from __future__ import annotations

import json
from typing import Any

from checkpointflow.persistence.store import RunRecord


def serialize_step_result(sr: dict[str, Any]) -> dict[str, Any]:
    """Convert a step_results row to a clean dict."""
    return {
        "step_id": sr["step_id"],
        "step_kind": sr["step_kind"],
        "exit_code": sr["exit_code"],
        "error_code": sr["error_code"],
        "error_message": sr["error_message"],
        "outputs": json.loads(sr["outputs_json"]) if sr["outputs_json"] else None,
        "stdout_path": sr["stdout_path"],
        "stderr_path": sr["stderr_path"],
        "created_at": sr["created_at"],
    }


def serialize_event(ev: dict[str, Any]) -> dict[str, Any]:
    """Convert an events row to a clean dict."""
    return {
        "event_name": ev["event_name"],
        "event_data": json.loads(ev["event_json"]),
        "step_id": ev.get("step_id"),
        "created_at": ev["created_at"],
    }


def workflow_metadata(run: RunRecord) -> dict[str, Any]:
    """Extract workflow metadata kwargs from a run record."""
    return {
        "workflow_id": run["workflow_id"],
        "workflow_name": run["workflow_name"],
        "workflow_description": run["workflow_description"],
        "workflow_version": run["workflow_version"],
    }
