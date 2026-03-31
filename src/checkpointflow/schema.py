from __future__ import annotations

import functools
import importlib.resources
import json
from typing import Any, cast

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]


@functools.cache
def load_workflow_schema() -> dict[str, Any]:
    schema_file = importlib.resources.files("checkpointflow.schemas").joinpath(
        "checkpointflow.schema.json"
    )
    return cast(dict[str, Any], json.loads(schema_file.read_text(encoding="utf-8")))


def validate_workflow_document(data: dict[str, Any]) -> list[str]:
    schema = load_workflow_schema()
    validator = Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(data)]
