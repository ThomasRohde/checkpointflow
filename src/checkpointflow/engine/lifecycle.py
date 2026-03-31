"""Lifecycle operations for workflow runs: delete and cancel."""

from __future__ import annotations

from pathlib import Path

from checkpointflow.models.envelope import Envelope
from checkpointflow.models.errors import ErrorCode, ExitCode
from checkpointflow.persistence.store import Store


def delete_run(
    run_id: str,
    *,
    base_dir: Path | None = None,
) -> Envelope:
    """Permanently delete a terminal run and all its data."""
    store = Store(base_dir=base_dir)
    run = store.get_run(run_id)

    if run is None:
        return Envelope.failure(
            command="delete",
            error_code=ErrorCode.ERR_RUN_NOT_FOUND,
            message=f"Run not found: {run_id}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    if run["status"] in ("created", "running", "waiting"):
        return Envelope.failure(
            command="delete",
            error_code=ErrorCode.ERR_RUN_NOT_WAITING,
            message=f"Cannot delete active run {run_id} (status: {run['status']})",
            exit_code=ExitCode.RUNTIME_ERROR,
            run_id=run_id,
        )

    store.delete_run(run_id)
    return Envelope.success(
        command="delete",
        run_id=run_id,
        workflow_id=run["workflow_id"],
        workflow_name=run.get("workflow_name"),
        workflow_description=run.get("workflow_description"),
        workflow_version=run["workflow_version"],
        result={"deleted": True},
    )


def cancel_run(
    run_id: str,
    reason: str,
    *,
    base_dir: Path | None = None,
) -> Envelope:
    """Cancel a waiting or running run."""
    store = Store(base_dir=base_dir)
    run = store.get_run(run_id)

    if run is None:
        return Envelope.failure(
            command="cancel",
            error_code=ErrorCode.ERR_RUN_NOT_FOUND,
            message=f"Run not found: {run_id}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    if run["status"] not in ("waiting", "running", "created"):
        return Envelope.failure(
            command="cancel",
            error_code=ErrorCode.ERR_RUN_NOT_WAITING,
            message=f"Run {run_id} cannot be cancelled (status: {run['status']})",
            exit_code=ExitCode.RUNTIME_ERROR,
            run_id=run_id,
        )

    store.update_run(run_id, status="cancelled")
    return Envelope.success(
        command="cancel",
        status="cancelled",
        exit_code=ExitCode.SUCCESS,
        run_id=run_id,
        workflow_id=run["workflow_id"],
        workflow_name=run.get("workflow_name"),
        workflow_description=run.get("workflow_description"),
        workflow_version=run["workflow_version"],
        result={"reason": reason},
    )
