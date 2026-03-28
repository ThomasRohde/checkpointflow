"""Integration tests for new step types wired into the runner."""

from __future__ import annotations

import json
from pathlib import Path

from checkpointflow.engine.runner import run_workflow

SWITCH_WORKFLOW = """\
schema_version: checkpointflow/v1
workflow:
  id: switch_test
  inputs:
    type: object
    required:
      - mode
    properties:
      mode:
        type: string
  steps:
    - id: decide
      kind: switch
      cases:
        - when: 'inputs.mode == "fast"'
          next: fast_path
        - when: 'inputs.mode == "slow"'
          next: slow_path
      default: fallback

    - id: fast_path
      kind: cli
      command: "printf '{\\\"result\\\": \\\"fast\\\"}'"
      outputs:
        type: object
        properties:
          result:
            type: string

    - id: done_fast
      kind: end
      result:
        result: ${steps.fast_path.outputs.result}

    - id: slow_path
      kind: cli
      command: "printf '{\\\"result\\\": \\\"slow\\\"}'"
      outputs:
        type: object
        properties:
          result:
            type: string

    - id: done_slow
      kind: end
      result:
        result: ${steps.slow_path.outputs.result}

    - id: fallback
      kind: end
      result:
        result: fallback
"""

FOREACH_WORKFLOW = """\
schema_version: checkpointflow/v1
workflow:
  id: foreach_test
  inputs:
    type: object
    required:
      - items
    properties:
      items:
        type: array
        items:
          type: string
  steps:
    - id: loop
      kind: foreach
      items: inputs.items
      body:
        - id: process
          kind: cli
          command: "echo processed"
    - id: done
      kind: end
"""

PARALLEL_WORKFLOW = """\
schema_version: checkpointflow/v1
workflow:
  id: parallel_test
  inputs:
    type: object
  steps:
    - id: par
      kind: parallel
      branches:
        - start_at: branch_a
        - start_at: branch_b
    - id: branch_a
      kind: cli
      command: "printf '{\\\"from\\\": \\\"a\\\"}'"
      outputs:
        type: object
    - id: branch_b
      kind: cli
      command: "printf '{\\\"from\\\": \\\"b\\\"}'"
      outputs:
        type: object
    - id: done
      kind: end
"""


def test_switch_workflow_fast_path(tmp_path: Path) -> None:
    wf = tmp_path / "wf.yaml"
    wf.write_text(SWITCH_WORKFLOW)
    env = run_workflow(wf, json.dumps({"mode": "fast"}), base_dir=tmp_path)
    assert env.ok is True
    assert env.result is not None
    assert env.result["result"] == "fast"


def test_switch_workflow_slow_path(tmp_path: Path) -> None:
    wf = tmp_path / "wf.yaml"
    wf.write_text(SWITCH_WORKFLOW)
    env = run_workflow(wf, json.dumps({"mode": "slow"}), base_dir=tmp_path)
    assert env.ok is True
    assert env.result is not None
    assert env.result["result"] == "slow"


def test_switch_workflow_default(tmp_path: Path) -> None:
    wf = tmp_path / "wf.yaml"
    wf.write_text(SWITCH_WORKFLOW)
    env = run_workflow(wf, json.dumps({"mode": "other"}), base_dir=tmp_path)
    assert env.ok is True
    assert env.result is not None
    assert env.result["result"] == "fallback"


def test_foreach_workflow(tmp_path: Path) -> None:
    wf = tmp_path / "wf.yaml"
    wf.write_text(FOREACH_WORKFLOW)
    env = run_workflow(wf, json.dumps({"items": ["a", "b", "c"]}), base_dir=tmp_path)
    assert env.ok is True
    assert env.status == "completed"


def test_parallel_workflow(tmp_path: Path) -> None:
    wf = tmp_path / "wf.yaml"
    wf.write_text(PARALLEL_WORKFLOW)
    env = run_workflow(wf, json.dumps({}), base_dir=tmp_path)
    assert env.ok is True
    assert env.status == "completed"
