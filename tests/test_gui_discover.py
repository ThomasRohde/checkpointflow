"""Tests for workflow discovery in the GUI API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

MINIMAL_WORKFLOW = """\
schema_version: checkpointflow/v1
workflow:
  id: test-wf
  name: Test Workflow
  steps:
    - id: s1
      kind: cli
      command: echo hello
"""


@pytest.fixture()
def cwd_dir(tmp_path: Path) -> Path:
    """Simulate a cwd with a .checkpointflow subdir."""
    cpf = tmp_path / "cwd"
    cpf.mkdir()
    return cpf


@pytest.fixture()
def base_dir(tmp_path: Path) -> Path:
    """Simulate the ~/.checkpointflow base dir."""
    bd = tmp_path / "home_cpf"
    bd.mkdir()
    return bd


def test_discover_finds_workflow_in_cwd_checkpointflow(cwd_dir: Path, base_dir: Path) -> None:
    """Workflows in cwd/.checkpointflow/ should be discovered."""
    from checkpointflow.gui.api import discover_workflows

    cpf = cwd_dir / ".checkpointflow"
    cpf.mkdir()
    (cpf / "my-flow.yaml").write_text(MINIMAL_WORKFLOW)

    with patch("checkpointflow.gui.api.Path.cwd", return_value=cwd_dir):
        result = discover_workflows(base_dir)

    names = [w["name"] for w in result]
    assert "my-flow" in names


def test_discover_finds_workflow_in_base_dir(cwd_dir: Path, base_dir: Path) -> None:
    """Workflows in base_dir (global) should be discovered."""
    from checkpointflow.gui.api import discover_workflows

    (base_dir / "global-flow.yaml").write_text(MINIMAL_WORKFLOW)

    with patch("checkpointflow.gui.api.Path.cwd", return_value=cwd_dir):
        result = discover_workflows(base_dir)

    names = [w["name"] for w in result]
    assert "global-flow" in names


def test_discover_does_not_recurse_into_deep_dirs(cwd_dir: Path, base_dir: Path) -> None:
    """Must NOT find workflows buried deep in cwd (e.g. node_modules)."""
    from checkpointflow.gui.api import discover_workflows

    deep = cwd_dir / "node_modules" / "some-pkg"
    deep.mkdir(parents=True)
    (deep / "workflow.yaml").write_text(MINIMAL_WORKFLOW)

    with patch("checkpointflow.gui.api.Path.cwd", return_value=cwd_dir):
        result = discover_workflows(base_dir)

    # The deeply nested file must NOT appear
    paths = [w["path"] for w in result]
    assert not any("node_modules" in p for p in paths)


def test_discover_returns_empty_when_no_workflows(cwd_dir: Path, base_dir: Path) -> None:
    """Empty directories should return an empty list, not hang."""
    from checkpointflow.gui.api import discover_workflows

    with patch("checkpointflow.gui.api.Path.cwd", return_value=cwd_dir):
        result = discover_workflows(base_dir)

    assert result == []


def test_discover_ignores_non_cpf_yaml(cwd_dir: Path, base_dir: Path) -> None:
    """YAML files without 'checkpointflow/v1' should be skipped."""
    from checkpointflow.gui.api import discover_workflows

    cpf = cwd_dir / ".checkpointflow"
    cpf.mkdir()
    (cpf / "random.yaml").write_text("name: not a workflow\n")

    with patch("checkpointflow.gui.api.Path.cwd", return_value=cwd_dir):
        result = discover_workflows(base_dir)

    assert result == []


def test_discover_deduplicates(cwd_dir: Path) -> None:
    """If cwd/.checkpointflow IS base_dir, workflows should appear once."""
    from checkpointflow.gui.api import discover_workflows

    cpf = cwd_dir / ".checkpointflow"
    cpf.mkdir()
    (cpf / "wf.yaml").write_text(MINIMAL_WORKFLOW)

    # base_dir = cwd/.checkpointflow → same location
    with patch("checkpointflow.gui.api.Path.cwd", return_value=cwd_dir):
        result = discover_workflows(cpf)

    assert len(result) == 1
