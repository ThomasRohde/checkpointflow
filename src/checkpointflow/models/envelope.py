from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class EnvelopeError(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    message: str
    step_id: str | None = None
    details: Any | None = None


class WaitResume(BaseModel):
    command: str


class WaitDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["external_event"] = "external_event"
    audience: Literal["user", "agent", "system"]
    event_name: str
    prompt: str | None = None
    summary: str | None = None
    input_schema: dict[str, Any]
    instructions: list[str] | None = None
    timeout_at: str | None = None
    risk_level: Literal["low", "medium", "high"] | None = None
    resume: WaitResume


class Envelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: Literal["checkpointflow-run/v1"] = "checkpointflow-run/v1"
    request_id: str | None = None
    ok: bool
    command: str
    status: Literal["created", "running", "waiting", "completed", "failed", "cancelled"]
    exit_code: int | None = None
    run_id: str | None = None
    workflow_id: str | None = None
    workflow_version: str | None = None
    current_step_id: str | None = None
    checkpoint_id: str | None = None
    started_at: str | None = None
    updated_at: str | None = None
    warnings: list[str] | None = None
    result: Any | None = None
    error: EnvelopeError | None = None
    wait: WaitDetail | None = None

    def to_json(self) -> str:
        return self.model_dump_json(exclude_none=True, indent=2)

    @classmethod
    def success(
        cls,
        command: str,
        *,
        status: str = "completed",
        exit_code: int = 0,
        **kwargs: Any,
    ) -> Envelope:
        return cls(
            ok=True,
            command=command,
            status=status,
            exit_code=exit_code,
            **kwargs,
        )

    @classmethod
    def failure(
        cls,
        command: str,
        error_code: str,
        message: str,
        exit_code: int,
        *,
        details: Any | None = None,
        **kwargs: Any,
    ) -> Envelope:
        return cls(
            ok=False,
            command=command,
            status="failed",
            exit_code=exit_code,
            error=EnvelopeError(code=error_code, message=message, details=details),
            **kwargs,
        )
