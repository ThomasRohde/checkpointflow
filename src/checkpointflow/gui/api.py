"""API route handlers for the checkpointflow GUI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from checkpointflow.models.workflow import WorkflowDocument
from checkpointflow.persistence.store import Store


def list_runs(store: Store) -> list[dict[str, Any]]:
    """List all runs from the store."""
    cursor = store._conn.execute(
        "SELECT run_id, workflow_id, workflow_version, workflow_path, "
        "status, current_step_id, created_at, updated_at "
        "FROM runs ORDER BY created_at DESC"
    )
    return [dict(row) for row in cursor.fetchall()]


def get_run_detail(store: Store, run_id: str) -> dict[str, Any] | None:
    """Get full run detail including step results and events."""
    run = store.get_run(run_id)
    if run is None:
        return None

    step_results = store.get_step_results(run_id)
    events = store.get_events(run_id)

    return {
        **dict(run),
        "inputs": json.loads(run["inputs_json"]),
        "step_outputs": json.loads(run["step_outputs_json"]),
        "result": json.loads(run["result_json"]) if run["result_json"] else None,
        "step_results": [
            {
                "step_id": sr["step_id"],
                "step_kind": sr["step_kind"],
                "exit_code": sr["exit_code"],
                "error_code": sr["error_code"],
                "error_message": sr["error_message"],
                "outputs": json.loads(sr["outputs_json"]) if sr["outputs_json"] else None,
                "stdout_path": sr["stdout_path"],
                "stderr_path": sr["stderr_path"],
                "execution_order": sr["execution_order"],
                "created_at": sr["created_at"],
            }
            for sr in step_results
        ],
        "events": [
            {
                "event_name": ev["event_name"],
                "event_data": json.loads(ev["event_json"]),
                "created_at": ev["created_at"],
            }
            for ev in events
        ],
    }


def delete_run(store: Store, run_id: str) -> dict[str, Any] | None:
    """Delete a run. Returns None if not found, raises PersistenceError if active."""
    run = store.get_run(run_id)
    if run is None:
        return None
    store.delete_run(run_id)
    return {"deleted": True, "run_id": run_id}


def bulk_delete_runs(store: Store, run_ids: list[str]) -> dict[str, list[str]]:
    """Delete multiple runs. Skips runs that are not found or are still active."""
    from checkpointflow.persistence.store import PersistenceError

    deleted: list[str] = []
    skipped: list[str] = []
    for run_id in run_ids:
        try:
            store.delete_run(run_id)
            deleted.append(run_id)
        except PersistenceError:
            skipped.append(run_id)
    return {"deleted": deleted, "skipped": skipped}


def _safe_path_component(value: str) -> bool:
    """Return True if *value* is safe to use as a single path component."""
    return ".." not in value and "/" not in value and "\\" not in value


def get_step_output(store: Store, run_id: str, step_id: str, stream: str) -> str | None:
    """Read stdout or stderr for a step."""
    if not (_safe_path_component(run_id) and _safe_path_component(step_id)):
        return None
    run_dir = store.base_dir / "runs" / run_id / stream
    path = run_dir / f"{step_id}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    return None


def discover_workflows(base_dir: Path) -> list[dict[str, str]]:
    """Find workflow YAML files in cwd/.checkpointflow and base_dir.

    Delegates to the shared :func:`checkpointflow.discovery.discover_workflows`
    and converts results to the dict format expected by the GUI API.
    """
    from checkpointflow.discovery import discover_workflows as _discover

    cwd = Path.cwd()
    search_dirs = [cwd / ".checkpointflow", base_dir]

    results: list[dict[str, str]] = []
    for wf in _discover(search_dirs):
        source = "cwd" if wf.path.resolve().is_relative_to(cwd.resolve()) else "home"
        results.append(
            {
                "path": str(wf.path.resolve()),
                "name": wf.path.stem,
                "source": source,
                "relative": wf.path.name,
            }
        )
    return results


def parse_workflow(path: str) -> dict[str, Any] | None:
    """Parse a workflow YAML file and return as a dict for graph rendering."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        doc = WorkflowDocument.model_validate(data)
        workflow = doc.workflow

        steps = []
        for i, step in enumerate(workflow.steps):
            step_data: dict[str, Any] = {
                "id": step.id,
                "kind": step.kind,
                "name": step.name or step.id,
                "description": step.description,
                "if": step.step_if,
                "index": i,
            }

            # Add kind-specific fields
            from checkpointflow.models.workflow import (
                ApiStep,
                AwaitEventStep,
                CliStep,
                EndStep,
                ForeachStep,
                ParallelStep,
                SwitchStep,
                WorkflowRefStep,
            )

            if isinstance(step, CliStep):
                step_data["command"] = step.command
                step_data["shell"] = step.shell
                step_data["cwd"] = step.cwd
            elif isinstance(step, AwaitEventStep):
                step_data["audience"] = step.audience
                step_data["event_name"] = step.event_name
                step_data["prompt"] = step.prompt
                step_data["transitions"] = (
                    [{"when": t.when, "next": t.next} for t in step.transitions]
                    if step.transitions
                    else None
                )
            elif isinstance(step, EndStep):
                step_data["result"] = step.result
            elif isinstance(step, SwitchStep):
                step_data["cases"] = [{"when": c.when, "next": c.next} for c in step.cases]
                step_data["default"] = step.default
            elif isinstance(step, ApiStep):
                step_data["method"] = step.method
                step_data["url"] = step.url
            elif isinstance(step, ForeachStep):
                step_data["items"] = step.items
            elif isinstance(step, ParallelStep):
                step_data["branches"] = [{"start_at": b.start_at} for b in step.branches]
            elif isinstance(step, WorkflowRefStep):
                step_data["workflow_ref"] = step.workflow_ref

            steps.append(step_data)

        return {
            "id": workflow.id,
            "name": workflow.name or workflow.id,
            "version": workflow.version,
            "description": workflow.description,
            "defaults": workflow.defaults,
            "inputs": workflow.inputs,
            "steps": steps,
            "path": path,
        }
    except Exception:
        return None
