from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from checkpointflow.schema import (
    load_envelope_schema,
    load_workflow_schema,
    validate_workflow_document,
)


def test_load_workflow_schema_returns_dict() -> None:
    schema = load_workflow_schema()
    assert isinstance(schema, dict)
    assert "$schema" in schema


def test_load_envelope_schema_returns_dict() -> None:
    schema = load_envelope_schema()
    assert isinstance(schema, dict)
    assert "$schema" in schema


def test_validate_valid_workflow_returns_no_errors(
    valid_workflow_dict: dict[str, Any],
) -> None:
    errors = validate_workflow_document(valid_workflow_dict)
    assert errors == []


def test_validate_invalid_workflow_returns_errors() -> None:
    errors = validate_workflow_document({"bad": "doc"})
    assert len(errors) > 0


def test_validate_missing_required_field() -> None:
    data = {"schema_version": "checkpointflow/v1", "workflow": {"id": "wf"}}
    errors = validate_workflow_document(data)
    assert any("inputs" in e or "steps" in e for e in errors)


def test_validate_example_workflow() -> None:
    example = Path("examples/publish-confluence-change.yaml")
    with example.open() as f:
        data = yaml.safe_load(f)
    errors = validate_workflow_document(data)
    assert errors == [], f"Example workflow should validate cleanly: {errors}"
