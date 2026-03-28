from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from checkpointflow.models.envelope import Envelope, WaitDetail, WaitResume
from checkpointflow.models.errors import ErrorCode, ExitCode
from checkpointflow.models.workflow import AwaitEventStep, WorkflowDocument
from checkpointflow.persistence.store import Store


def query_status(
    run_id: str,
    *,
    base_dir: Path | None = None,
) -> Envelope:
    """Query the current status of a run."""
    store = Store(base_dir=base_dir)
    run = store.get_run(run_id)

    if run is None:
        return Envelope.failure(
            command="status",
            error_code=ErrorCode.ERR_RUN_NOT_FOUND,
            message=f"Run not found: {run_id}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    status: str = run["status"]
    exit_code = _status_to_exit_code(status)

    kwargs: dict[str, Any] = {
        "run_id": run_id,
        "workflow_id": run["workflow_id"],
        "workflow_version": run["workflow_version"],
        "current_step_id": run["current_step_id"],
    }

    if status == "waiting" and run["expected_event_name"]:
        input_schema = (
            json.loads(run["expected_event_schema"])
            if run["expected_event_schema"]
            else {"type": "object"}
        )
        resume_cmd = (
            f"cpf resume --run-id {run_id} --event {run['expected_event_name']} --input @event.json"
        )
        # Try to load prompt/audience from the workflow file
        audience: str = "user"
        prompt: str | None = None
        summary: str | None = None
        risk_level: str | None = None
        workflow_path = Path(run["workflow_path"])
        if workflow_path.exists() and run["current_step_id"]:
            try:
                doc = WorkflowDocument.model_validate(
                    yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
                )
                for s in doc.workflow.steps:
                    if s.id == run["current_step_id"] and isinstance(s, AwaitEventStep):
                        audience = s.audience
                        prompt = s.prompt
                        summary = s.summary
                        risk_level = s.risk_level
                        break
            except Exception:
                pass
        kwargs["wait"] = WaitDetail(
            audience=audience,
            event_name=run["expected_event_name"],
            prompt=prompt,
            summary=summary,
            input_schema=input_schema,
            instructions=[
                "Ask the intended audience for input using the prompt.",
                "Collect JSON that matches input_schema.",
                "Resume with the provided run_id and event_name.",
            ],
            risk_level=risk_level,
            resume=WaitResume(command=resume_cmd),
        )

    if status == "completed" and run["result_json"]:
        kwargs["result"] = json.loads(run["result_json"])

    return Envelope.success(
        command="status",
        status=status,
        exit_code=exit_code,
        **kwargs,
    )


def query_inspect(
    run_id: str,
    *,
    base_dir: Path | None = None,
) -> Envelope:
    """Query detailed execution history of a run."""
    store = Store(base_dir=base_dir)
    run = store.get_run(run_id)

    if run is None:
        return Envelope.failure(
            command="inspect",
            error_code=ErrorCode.ERR_RUN_NOT_FOUND,
            message=f"Run not found: {run_id}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    step_results = store.get_step_results(run_id)
    events = store.get_events(run_id)

    detail: dict[str, Any] = {
        "inputs": json.loads(run["inputs_json"]),
        "step_outputs": json.loads(run["step_outputs_json"]),
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

    status: str = run["status"]
    return Envelope.success(
        command="inspect",
        status=status,
        exit_code=_status_to_exit_code(status),
        run_id=run_id,
        workflow_id=run["workflow_id"],
        workflow_version=run["workflow_version"],
        current_step_id=run["current_step_id"],
        result=detail,
    )


def _status_to_exit_code(status: str) -> int:
    return {
        "completed": ExitCode.SUCCESS,
        "waiting": ExitCode.WAITING,
        "failed": ExitCode.STEP_FAILED,
        "cancelled": ExitCode.CANCELLED,
    }.get(status, ExitCode.SUCCESS)
