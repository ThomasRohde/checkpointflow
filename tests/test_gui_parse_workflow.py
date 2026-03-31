"""Tests for parse_workflow in gui/api.py."""

from __future__ import annotations

from pathlib import Path

from checkpointflow.gui.api import parse_workflow

CLI_WORKFLOW = """\
schema_version: checkpointflow/v1
workflow:
  id: test-wf
  name: Test Workflow
  version: "1.0"
  description: A test
  inputs:
    type: object
  steps:
    - id: s1
      kind: cli
      command: echo hello
    - id: done
      kind: end
      result:
        status: ok
"""


def test_parse_workflow_returns_dict(tmp_path: Path) -> None:
    f = tmp_path / "wf.yaml"
    f.write_text(CLI_WORKFLOW)
    result = parse_workflow(str(f))
    assert result is not None
    assert result["id"] == "test-wf"
    assert result["name"] == "Test Workflow"
    assert len(result["steps"]) == 2


def test_parse_workflow_nonexistent_returns_none() -> None:
    assert parse_workflow("/nonexistent/path.yaml") is None


def test_parse_workflow_invalid_yaml_returns_none(tmp_path: Path) -> None:
    f = tmp_path / "bad.yaml"
    f.write_text("not: valid: workflow: - [")
    assert parse_workflow(str(f)) is None


def test_parse_workflow_cli_step_fields(tmp_path: Path) -> None:
    f = tmp_path / "wf.yaml"
    f.write_text(CLI_WORKFLOW)
    result = parse_workflow(str(f))
    assert result is not None
    cli_step = result["steps"][0]
    assert cli_step["kind"] == "cli"
    assert cli_step["command"] == "echo hello"


def test_parse_workflow_end_step_fields(tmp_path: Path) -> None:
    f = tmp_path / "wf.yaml"
    f.write_text(CLI_WORKFLOW)
    result = parse_workflow(str(f))
    assert result is not None
    end_step = result["steps"][1]
    assert end_step["kind"] == "end"
    assert end_step["result"] == {"status": "ok"}


def test_parse_workflow_switch_step(tmp_path: Path) -> None:
    f = tmp_path / "wf.yaml"
    f.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: sw
  inputs:
    type: object
  steps:
    - id: decide
      kind: switch
      cases:
        - when: inputs.x == "a"
          next: done
      default: done
    - id: done
      kind: end
""")
    result = parse_workflow(str(f))
    assert result is not None
    sw = result["steps"][0]
    assert sw["kind"] == "switch"
    assert len(sw["cases"]) == 1
    assert sw["default"] == "done"


def test_parse_workflow_api_step(tmp_path: Path) -> None:
    f = tmp_path / "wf.yaml"
    f.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: api-wf
  inputs:
    type: object
  steps:
    - id: fetch
      kind: api
      method: GET
      url: http://example.com
    - id: done
      kind: end
""")
    result = parse_workflow(str(f))
    assert result is not None
    api = result["steps"][0]
    assert api["method"] == "GET"
    assert api["url"] == "http://example.com"


def test_parse_workflow_await_event_step(tmp_path: Path) -> None:
    f = tmp_path / "wf.yaml"
    f.write_text("""\
schema_version: checkpointflow/v1
workflow:
  id: await-wf
  inputs:
    type: object
  steps:
    - id: wait
      kind: await_event
      event_name: approval
      audience: user
      prompt: Please approve
      input_schema:
        type: object
    - id: done
      kind: end
""")
    result = parse_workflow(str(f))
    assert result is not None
    await_step = result["steps"][0]
    assert await_step["kind"] == "await_event"
    assert await_step["event_name"] == "approval"
