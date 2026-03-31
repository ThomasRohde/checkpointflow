from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from checkpointflow.models.workflow import (
    AwaitEventStep,
    CliStep,
    EndStep,
    WorkflowDocument,
    find_duplicate_step_ids,
)


def test_minimal_cli_step_parses() -> None:
    step = CliStep.model_validate({"id": "a", "kind": "cli", "command": "echo hi"})
    assert step.id == "a"
    assert step.kind == "cli"
    assert step.command == "echo hi"


def test_cli_step_with_if_field() -> None:
    step = CliStep.model_validate(
        {"id": "a", "kind": "cli", "command": "echo", "if": "inputs.flag == true"}
    )
    assert step.step_if == "inputs.flag == true"


def test_cli_step_serializes_if_as_alias() -> None:
    step = CliStep.model_validate({"id": "a", "kind": "cli", "command": "echo", "if": "expr"})
    dumped = step.model_dump(by_alias=True)
    assert "if" in dumped
    assert "step_if" not in dumped


def test_end_step_parses() -> None:
    step = EndStep.model_validate({"id": "done", "kind": "end"})
    assert step.id == "done"
    assert step.kind == "end"


def test_end_step_with_result() -> None:
    step = EndStep.model_validate({"id": "done", "kind": "end", "result": {"status": "rejected"}})
    assert step.result == {"status": "rejected"}


def test_await_event_step_parses() -> None:
    data = {
        "id": "approval",
        "kind": "await_event",
        "audience": "user",
        "event_name": "approval_decision",
        "input_schema": {"type": "object"},
    }
    step = AwaitEventStep.model_validate(data)
    assert step.id == "approval"
    assert step.audience == "user"
    assert step.event_name == "approval_decision"


def test_minimal_workflow_document_parses(
    valid_workflow_dict: dict[str, Any],
) -> None:
    doc = WorkflowDocument.model_validate(valid_workflow_dict)
    assert doc.schema_version == "checkpointflow/v1"
    assert doc.workflow.id == "test_workflow"
    assert len(doc.workflow.steps) == 2


def test_step_discriminated_union(valid_workflow_dict: dict[str, Any]) -> None:
    doc = WorkflowDocument.model_validate(valid_workflow_dict)
    assert isinstance(doc.workflow.steps[0], CliStep)
    assert isinstance(doc.workflow.steps[1], EndStep)


def test_example_workflow_parses() -> None:
    example = Path("examples/publish-confluence-change.yaml")
    with example.open() as f:
        data = yaml.safe_load(f)
    doc = WorkflowDocument.model_validate(data)
    assert doc.workflow.id == "publish_confluence_change"
    assert len(doc.workflow.steps) == 4
    assert isinstance(doc.workflow.steps[1], AwaitEventStep)


def test_workflow_document_rejects_unknown_kind() -> None:
    data = {
        "schema_version": "checkpointflow/v1",
        "workflow": {
            "id": "wf",
            "inputs": {"type": "object"},
            "steps": [{"id": "s", "kind": "unknown"}],
        },
    }
    with pytest.raises(ValidationError):
        WorkflowDocument.model_validate(data)


def test_workflow_document_rejects_missing_steps() -> None:
    data = {
        "schema_version": "checkpointflow/v1",
        "workflow": {"id": "wf", "inputs": {"type": "object"}},
    }
    with pytest.raises(ValidationError):
        WorkflowDocument.model_validate(data)


# --- find_duplicate_step_ids ---


def test_find_duplicate_step_ids_none() -> None:
    assert find_duplicate_step_ids(["a", "b", "c"]) == []


def test_find_duplicate_step_ids_found() -> None:
    assert find_duplicate_step_ids(["a", "b", "a", "c", "b"]) == ["a", "b"]


def test_find_duplicate_step_ids_empty() -> None:
    assert find_duplicate_step_ids([]) == []
