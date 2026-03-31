from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from checkpointflow.models.state import RunContext

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


@pytest.fixture()
def run_ctx(tmp_path: Path) -> Callable[..., RunContext]:
    """Factory fixture for RunContext with auto-created stdout/stderr dirs."""

    def _make(
        *,
        inputs: dict[str, Any] | None = None,
        step_outputs: dict[str, dict[str, Any]] | None = None,
        defaults: dict[str, Any] | None = None,
    ) -> RunContext:
        run_dir = tmp_path
        (run_dir / "stdout").mkdir(parents=True, exist_ok=True)
        (run_dir / "stderr").mkdir(parents=True, exist_ok=True)
        return RunContext(
            run_id="test-run",
            inputs=inputs or {},
            step_outputs=step_outputs or {},
            run_dir=run_dir,
            defaults=defaults or {},
        )

    return _make


@pytest.fixture()
def write_workflow(tmp_path: Path) -> Callable[..., Path]:
    """Factory fixture for writing workflow YAML files."""

    def _make(steps_yaml: str, *, inputs_schema: str = "type: object") -> Path:
        content = (
            "schema_version: checkpointflow/v1\n"
            "workflow:\n"
            "  id: test_wf\n"
            "  version: '1.0'\n"
            f"  inputs:\n    {inputs_schema}\n"
            f"  steps:\n{steps_yaml}\n"
        )
        out = tmp_path / "workflow.yaml"
        out.write_text(content)
        return out

    return _make
