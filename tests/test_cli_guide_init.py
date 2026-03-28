from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from checkpointflow.cli import app

runner = CliRunner()


# --- cpf guide ---


def test_guide_exits_zero() -> None:
    result = runner.invoke(app, ["guide"])
    assert result.exit_code == 0


def test_guide_contains_checkpointflow() -> None:
    result = runner.invoke(app, ["guide"])
    assert "checkpointflow" in result.stdout


def test_guide_contains_step_kinds() -> None:
    result = runner.invoke(app, ["guide"])
    assert "await_event" in result.stdout
    assert "cli" in result.stdout


# --- cpf init ---


def test_init_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "new_workflow.yaml"
    result = runner.invoke(app, ["init", "--file", str(out)])
    assert result.exit_code == 0
    assert out.exists()


def test_init_file_validates(tmp_path: Path) -> None:
    out = tmp_path / "new_workflow.yaml"
    runner.invoke(app, ["init", "--file", str(out)])
    val_result = runner.invoke(app, ["validate", "-f", str(out)])
    assert val_result.exit_code == 0


def test_init_file_has_schema_version(tmp_path: Path) -> None:
    out = tmp_path / "new_workflow.yaml"
    runner.invoke(app, ["init", "--file", str(out)])
    content = out.read_text()
    assert "schema_version: checkpointflow/v1" in content


def test_init_file_exists_fails(tmp_path: Path) -> None:
    out = tmp_path / "existing.yaml"
    out.write_text("existing content")
    result = runner.invoke(app, ["init", "--file", str(out)])
    assert result.exit_code != 0
    assert out.read_text() == "existing content"


def test_init_force_overwrites(tmp_path: Path) -> None:
    out = tmp_path / "existing.yaml"
    out.write_text("old")
    result = runner.invoke(app, ["init", "--file", str(out), "--force"])
    assert result.exit_code == 0
    assert "schema_version" in out.read_text()


def test_init_output_is_json_envelope(tmp_path: Path) -> None:
    out = tmp_path / "wf.yaml"
    result = runner.invoke(app, ["init", "--file", str(out)])
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["command"] == "init"
