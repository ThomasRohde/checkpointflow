from __future__ import annotations

import json

from checkpointflow.models.envelope import Envelope, EnvelopeError


def test_success_envelope_serializes_to_json() -> None:
    envelope = Envelope(ok=True, command="validate", status="completed")
    data = json.loads(envelope.to_json())
    assert data["ok"] is True
    assert data["command"] == "validate"
    assert data["status"] == "completed"
    assert data["schema_version"] == "checkpointflow-run/v1"


def test_failure_envelope_includes_error() -> None:
    error = EnvelopeError(code="ERR_FILE_NOT_FOUND", message="not found")
    envelope = Envelope(ok=False, command="validate", status="failed", error=error)
    data = json.loads(envelope.to_json())
    assert data["ok"] is False
    assert data["error"]["code"] == "ERR_FILE_NOT_FOUND"
    assert data["error"]["message"] == "not found"


def test_envelope_excludes_none_fields() -> None:
    envelope = Envelope(ok=True, command="validate", status="completed")
    data = json.loads(envelope.to_json())
    assert "error" not in data
    assert "run_id" not in data
    assert "wait" not in data


def test_envelope_success_factory() -> None:
    envelope = Envelope.success(
        command="validate",
        workflow_id="test_wf",
        workflow_version="1.0",
    )
    assert envelope.ok is True
    assert envelope.status == "completed"
    assert envelope.command == "validate"
    assert envelope.workflow_id == "test_wf"
    assert envelope.workflow_version == "1.0"
    assert envelope.exit_code == 0


def test_envelope_failure_factory() -> None:
    envelope = Envelope.failure(
        command="validate",
        error_code="ERR_VALIDATION_WORKFLOW",
        message="bad workflow",
        exit_code=10,
    )
    assert envelope.ok is False
    assert envelope.status == "failed"
    assert envelope.error is not None
    assert envelope.error.code == "ERR_VALIDATION_WORKFLOW"
    assert envelope.error.message == "bad workflow"
    assert envelope.exit_code == 10


def test_envelope_schema_version_is_fixed() -> None:
    envelope = Envelope(ok=True, command="test", status="completed")
    assert envelope.schema_version == "checkpointflow-run/v1"
