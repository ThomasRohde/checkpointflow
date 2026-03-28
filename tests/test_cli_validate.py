from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from checkpointflow.cli import app

runner = CliRunner()


def test_validate_valid_file_exits_zero(valid_workflow_yaml: Path) -> None:
    result = runner.invoke(app, ["validate", "-f", str(valid_workflow_yaml)])
    assert result.exit_code == 0


def test_validate_valid_file_outputs_json_envelope(valid_workflow_yaml: Path) -> None:
    result = runner.invoke(app, ["validate", "-f", str(valid_workflow_yaml)])
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["command"] == "validate"
    assert envelope["status"] == "completed"
    assert envelope["schema_version"] == "checkpointflow-run/v1"


def test_validate_valid_file_includes_workflow_id(valid_workflow_yaml: Path) -> None:
    result = runner.invoke(app, ["validate", "-f", str(valid_workflow_yaml)])
    envelope = json.loads(result.stdout)
    assert envelope["workflow_id"] == "test_workflow"


def test_validate_nonexistent_file_exits_ten(tmp_path: Path) -> None:
    result = runner.invoke(app, ["validate", "-f", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 10


def test_validate_nonexistent_file_error_envelope(tmp_path: Path) -> None:
    result = runner.invoke(app, ["validate", "-f", str(tmp_path / "nope.yaml")])
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "ERR_FILE_NOT_FOUND"


def test_validate_invalid_yaml_exits_ten(broken_yaml: Path) -> None:
    result = runner.invoke(app, ["validate", "-f", str(broken_yaml)])
    assert result.exit_code == 10


def test_validate_invalid_yaml_error_code(broken_yaml: Path) -> None:
    result = runner.invoke(app, ["validate", "-f", str(broken_yaml)])
    envelope = json.loads(result.stdout)
    assert envelope["error"]["code"] == "ERR_YAML_PARSE"


def test_validate_invalid_schema_exits_ten(invalid_workflow_yaml: Path) -> None:
    result = runner.invoke(app, ["validate", "-f", str(invalid_workflow_yaml)])
    assert result.exit_code == 10


def test_validate_invalid_schema_error_code(invalid_workflow_yaml: Path) -> None:
    result = runner.invoke(app, ["validate", "-f", str(invalid_workflow_yaml)])
    envelope = json.loads(result.stdout)
    assert envelope["error"]["code"] == "ERR_VALIDATION_WORKFLOW"


def test_validate_error_envelope_includes_details(
    invalid_workflow_yaml: Path,
) -> None:
    result = runner.invoke(app, ["validate", "-f", str(invalid_workflow_yaml)])
    envelope = json.loads(result.stdout)
    assert envelope["error"]["details"] is not None


def test_validate_example_workflow_succeeds() -> None:
    result = runner.invoke(app, ["validate", "-f", "examples/publish-confluence-change.yaml"])
    assert result.exit_code == 0
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["workflow_id"] == "publish_confluence_change"
