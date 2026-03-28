from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

VALID_WORKFLOW_YAML = """\
schema_version: checkpointflow/v1
workflow:
  id: test_workflow
  inputs:
    type: object
  steps:
    - id: hello
      kind: cli
      command: echo hello
    - id: done
      kind: end
"""

INVALID_SCHEMA_YAML = """\
schema_version: checkpointflow/v1
workflow:
  id: bad_workflow
"""

BROKEN_YAML = """\
schema_version: checkpointflow/v1
workflow:
  steps:
    - id: [unterminated
"""


@pytest.fixture()
def valid_workflow_dict() -> dict[str, Any]:
    return {
        "schema_version": "checkpointflow/v1",
        "workflow": {
            "id": "test_workflow",
            "inputs": {"type": "object"},
            "steps": [
                {"id": "hello", "kind": "cli", "command": "echo hello"},
                {"id": "done", "kind": "end"},
            ],
        },
    }


@pytest.fixture()
def valid_workflow_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "valid.yaml"
    p.write_text(VALID_WORKFLOW_YAML)
    return p


@pytest.fixture()
def invalid_workflow_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "invalid.yaml"
    p.write_text(INVALID_SCHEMA_YAML)
    return p


@pytest.fixture()
def broken_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "broken.yaml"
    p.write_text(BROKEN_YAML)
    return p
