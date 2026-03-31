from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from checkpointflow.cli import app

runner = CliRunner()

WORKFLOW_A = """\
schema_version: checkpointflow/v1
workflow:
  id: workflow_a
  name: Workflow Alpha
  description: First test workflow for listing.
  version: "1.0.0"
  inputs:
    type: object
  steps:
    - id: done
      kind: end
"""

WORKFLOW_B = """\
schema_version: checkpointflow/v1
workflow:
  id: workflow_b
  name: Workflow Beta
  description: Second test workflow with details.
  version: "2.0.0"
  inputs:
    type: object
    required: [project_dir]
    properties:
      project_dir:
        type: string
        description: Absolute path to the repo root
      verbose:
        type: boolean
        description: Enable verbose output
  steps:
    - id: check
      kind: cli
      name: Run checks
      command: echo ok
    - id: review
      kind: await_event
      name: Human review
      audience: user
    - id: done
      kind: end
"""

INVALID_YAML = """\
schema_version: checkpointflow/v1
workflow:
  steps:
    - id: [unterminated
"""


def _make_workflow_dir(base: Path, *yamls: tuple[str, str]) -> Path:
    cpf_dir = base / ".checkpointflow"
    cpf_dir.mkdir()
    for name, content in yamls:
        (cpf_dir / name).write_text(content)
    return cpf_dir


def test_flows_lists_ids_and_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_workflow_dir(tmp_path, ("a.yaml", WORKFLOW_A), ("b.yaml", WORKFLOW_B))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "fakehome"))

    result = runner.invoke(app, ["flows"])
    assert result.exit_code == 0
    # Each entry should clearly show id and name on labeled lines
    assert "id: workflow_a" in result.stdout
    assert "name: Workflow Alpha" in result.stdout
    assert "id: workflow_b" in result.stdout
    assert "name: Workflow Beta" in result.stdout


def test_flows_list_shows_hint_footer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_workflow_dir(tmp_path, ("a.yaml", WORKFLOW_A))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "fakehome"))

    result = runner.invoke(app, ["flows"])
    assert result.exit_code == 0
    assert "cpf flows --detail <id>" in result.stdout
    assert "cpf run" in result.stdout


def test_flows_shows_no_workflows_found_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "fakehome"))

    result = runner.invoke(app, ["flows"])
    assert result.exit_code == 0
    assert "No workflows found" in result.stdout


def test_flows_detail_shows_full_info_for_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_workflow_dir(tmp_path, ("a.yaml", WORKFLOW_A), ("b.yaml", WORKFLOW_B))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "fakehome"))

    result = runner.invoke(app, ["flows", "--detail", "workflow_b"])
    assert result.exit_code == 0
    out = result.stdout

    # Identity
    assert "id: workflow_b" in out
    assert "name: Workflow Beta" in out
    assert "version: 2.0.0" in out
    assert "description:" in out

    # Inputs section with required/optional distinction
    assert "inputs:" in out
    assert "project_dir" in out
    assert "(required)" in out
    assert "verbose" in out

    # Steps overview
    assert "steps:" in out
    assert "check" in out
    assert "cli" in out
    assert "review" in out
    assert "await_event" in out

    # Run command uses -f with the actual path
    assert "cpf run -f" in out
    assert "--input" in out

    # Does NOT leak other workflows
    assert "Workflow Alpha" not in out


def test_flows_detail_path_only_in_run_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_workflow_dir(tmp_path, ("a.yaml", WORKFLOW_A))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "fakehome"))

    result = runner.invoke(app, ["flows", "--detail", "workflow_a"])
    assert result.exit_code == 0
    # The path should only appear inside the run command, not on its own line
    for line in result.stdout.splitlines():
        if ".checkpointflow" in line:
            assert line.strip().startswith("run:")


def test_flows_detail_by_name_is_case_insensitive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_workflow_dir(tmp_path, ("a.yaml", WORKFLOW_A))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "fakehome"))

    result = runner.invoke(app, ["flows", "--detail", "workflow alpha"])
    assert result.exit_code == 0
    assert "Workflow Alpha" in result.stdout


def test_flows_detail_not_found_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_workflow_dir(tmp_path, ("a.yaml", WORKFLOW_A))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "fakehome"))

    result = runner.invoke(app, ["flows", "--detail", "nonexistent"])
    assert result.exit_code == 1
    assert "No workflow matching" in result.stdout


def test_flows_searches_cwd_checkpointflow_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_workflow_dir(tmp_path, ("a.yaml", WORKFLOW_A))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "fakehome"))

    result = runner.invoke(app, ["flows"])
    assert result.exit_code == 0
    assert "workflow_a" in result.stdout


def test_flows_searches_global_checkpointflow_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    _make_workflow_dir(fake_home, ("b.yaml", WORKFLOW_B))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    result = runner.invoke(app, ["flows"])
    assert result.exit_code == 0
    assert "workflow_b" in result.stdout


def test_flows_combines_local_and_global_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_workflow_dir(tmp_path, ("a.yaml", WORKFLOW_A))
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    _make_workflow_dir(fake_home, ("b.yaml", WORKFLOW_B))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    result = runner.invoke(app, ["flows"])
    assert result.exit_code == 0
    assert "workflow_a" in result.stdout
    assert "workflow_b" in result.stdout


def test_flows_skips_invalid_yaml_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_workflow_dir(
        tmp_path,
        ("good.yaml", WORKFLOW_A),
        ("bad.yaml", INVALID_YAML),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "fakehome"))

    result = runner.invoke(app, ["flows"])
    assert result.exit_code == 0
    assert "workflow_a" in result.stdout


def test_flows_deduplicates_when_cwd_equals_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_workflow_dir(tmp_path, ("a.yaml", WORKFLOW_A))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    result = runner.invoke(app, ["flows"])
    assert result.exit_code == 0
    assert result.stdout.strip().count("workflow_a") == 1


def test_flows_discovers_yml_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cpf_dir = tmp_path / ".checkpointflow"
    cpf_dir.mkdir()
    (cpf_dir / "beta.yml").write_text(WORKFLOW_B)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "fakehome"))

    result = runner.invoke(app, ["flows"])
    assert result.exit_code == 0
    assert "workflow_b" in result.stdout


def test_flows_shows_help_text() -> None:
    result = runner.invoke(app, ["flows", "--help"])
    assert result.exit_code == 0
    assert "flows" in result.stdout.lower()
