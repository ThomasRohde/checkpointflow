"""Tests for the shared workflow discovery module."""

from __future__ import annotations

from pathlib import Path

from checkpointflow.discovery import discover_workflows


def _write_valid_workflow(path: Path, wf_id: str = "test_wf") -> Path:
    path.write_text(
        f"""\
workflow:
  id: {wf_id}
  name: Test Workflow
  version: "1.0"
  description: A test
  steps:
    - id: done
      kind: end
""",
        encoding="utf-8",
    )
    return path


def test_discover_empty_dir(tmp_path: Path) -> None:
    d = tmp_path / "empty"
    d.mkdir()
    assert discover_workflows([d]) == []


def test_discover_nonexistent_dir(tmp_path: Path) -> None:
    assert discover_workflows([tmp_path / "no_such_dir"]) == []


def test_discover_finds_yaml(tmp_path: Path) -> None:
    d = tmp_path / ".checkpointflow"
    d.mkdir()
    _write_valid_workflow(d / "flow.yaml")
    results = discover_workflows([d])
    assert len(results) == 1
    assert results[0].workflow_id == "test_wf"
    assert results[0].name == "Test Workflow"


def test_discover_finds_yml_extension(tmp_path: Path) -> None:
    d = tmp_path / "workflows"
    d.mkdir()
    _write_valid_workflow(d / "flow.yml")
    results = discover_workflows([d])
    assert len(results) == 1


def test_discover_skips_invalid_yaml(tmp_path: Path) -> None:
    d = tmp_path / "workflows"
    d.mkdir()
    (d / "bad.yaml").write_text("{{{{not yaml", encoding="utf-8")
    _write_valid_workflow(d / "good.yaml")
    results = discover_workflows([d])
    assert len(results) == 1
    assert results[0].workflow_id == "test_wf"


def test_discover_skips_non_workflow_yaml(tmp_path: Path) -> None:
    d = tmp_path / "workflows"
    d.mkdir()
    (d / "config.yaml").write_text("key: value\n", encoding="utf-8")
    _write_valid_workflow(d / "real.yaml")
    results = discover_workflows([d])
    assert len(results) == 1


def test_discover_deduplicates_by_resolved_path(tmp_path: Path) -> None:
    d = tmp_path / "workflows"
    d.mkdir()
    _write_valid_workflow(d / "flow.yaml")
    # Pass the same dir twice — should only find one
    results = discover_workflows([d, d])
    assert len(results) == 1


def test_discover_uses_stem_when_no_name_or_id(tmp_path: Path) -> None:
    d = tmp_path / "workflows"
    d.mkdir()
    (d / "my_flow.yaml").write_text(
        "workflow:\n  steps:\n    - id: done\n      kind: end\n",
        encoding="utf-8",
    )
    results = discover_workflows([d])
    assert len(results) == 1
    assert results[0].name == "my_flow"
    assert results[0].workflow_id == ""


def test_discover_multiple_dirs(tmp_path: Path) -> None:
    d1 = tmp_path / "dir1"
    d2 = tmp_path / "dir2"
    d1.mkdir()
    d2.mkdir()
    _write_valid_workflow(d1 / "a.yaml", wf_id="wf_a")
    _write_valid_workflow(d2 / "b.yaml", wf_id="wf_b")
    results = discover_workflows([d1, d2])
    assert len(results) == 2
    ids = {r.workflow_id for r in results}
    assert ids == {"wf_a", "wf_b"}
