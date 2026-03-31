from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from checkpointflow.models.workflow import WorkflowDocument
from checkpointflow.schema import (
    load_workflow_schema,
    validate_workflow_document,
)


def test_load_workflow_schema_returns_dict() -> None:
    schema = load_workflow_schema()
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


def test_validate_cpf_feature_development_workflow() -> None:
    example = Path("examples/cpf_feature_development.yaml")
    with example.open() as f:
        data = yaml.safe_load(f)
    errors = validate_workflow_document(data)
    assert errors == [], f"Feature development workflow should validate cleanly: {errors}"


# --- Schema drift detection ---


def test_pydantic_fields_covered_by_json_schema() -> None:
    """Ensure the checked-in JSON schema covers the same fields as the Pydantic models."""
    pydantic_schema = WorkflowDocument.model_json_schema()
    json_schema = load_workflow_schema()

    # Extract workflow properties from both schemas
    pydantic_wf = pydantic_schema["$defs"]["Workflow"]["properties"]
    json_wf = json_schema["$defs"]["workflow"]["properties"]

    pydantic_keys = set(pydantic_wf.keys())
    json_keys = set(json_wf.keys())

    missing_from_json = pydantic_keys - json_keys
    missing_from_pydantic = json_keys - pydantic_keys

    assert not missing_from_json, (
        f"Pydantic Workflow has fields not in JSON schema: {missing_from_json}"
    )
    assert not missing_from_pydantic, (
        f"JSON schema has fields not in Pydantic Workflow: {missing_from_pydantic}"
    )
