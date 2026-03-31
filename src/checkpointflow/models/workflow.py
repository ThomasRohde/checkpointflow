from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Success(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    exit_codes: list[int] | None = None
    status_codes: list[int] | None = None


class Transition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    when: str
    next: str


class OnTimeout(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    next: str | None = None


class BaseStepFields(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str | None = None
    description: str | None = None
    step_if: str | None = Field(None, alias="if")
    timeout_seconds: int | None = None
    risk_level: Literal["low", "medium", "high"] | None = None
    outputs: dict[str, Any] | None = None
    inputs: dict[str, Any] | None = None
    tags: list[str] | None = None


class CliStep(BaseStepFields):
    kind: Literal["cli"]
    command: str | list[str]
    shell: str | None = None
    cwd: str | None = None
    success: Success | None = None


class ApiStep(BaseStepFields):
    kind: Literal["api"]
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    url: str
    headers: dict[str, Any] | None = None
    body: Any | None = None
    success: Success | None = None


class AwaitEventStep(BaseStepFields):
    kind: Literal["await_event"]
    audience: Literal["user", "agent", "system"]
    event_name: str
    prompt: str | None = None
    summary: str | None = None
    input_schema: dict[str, Any]
    transitions: list[Transition] | None = None
    on_timeout: OnTimeout | None = None


class WorkflowRefStep(BaseStepFields):
    kind: Literal["workflow"]
    workflow_ref: str


class SwitchStep(BaseStepFields):
    kind: Literal["switch"]
    cases: list[Transition]
    default: str | None = None


class ParallelBranch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start_at: str


class ForeachStep(BaseStepFields):
    kind: Literal["foreach"]
    items: str
    workflow_ref: str | None = None
    body: list[dict[str, Any]] | None = None


class ParallelStep(BaseStepFields):
    kind: Literal["parallel"]
    branches: list[ParallelBranch]


class EndStep(BaseStepFields):
    kind: Literal["end"]
    result: Any | None = None


Step = Annotated[
    CliStep
    | ApiStep
    | AwaitEventStep
    | WorkflowRefStep
    | SwitchStep
    | ForeachStep
    | ParallelStep
    | EndStep,
    Field(discriminator="kind"),
]


def find_duplicate_step_ids(step_ids: Sequence[str]) -> list[str]:
    """Return step IDs that appear more than once, in order of first duplicate."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for sid in step_ids:
        if sid in seen and sid not in duplicates:
            duplicates.append(sid)
        seen.add(sid)
    return duplicates


class Workflow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str | None = None
    description: str | None = None
    version: str | None = None
    defaults: dict[str, Any] | None = None
    inputs: dict[str, Any]
    steps: list[Step]
    outputs: dict[str, Any] | None = None


class WorkflowDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: Literal["checkpointflow/v1"]
    workflow: Workflow
