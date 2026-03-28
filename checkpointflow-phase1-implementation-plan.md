# checkpointflow phase-1 implementation plan

Version: 0.1.0  
Target: Minimal but real runtime

## Objective

Build a first package release that proves checkpointflow works end to end as both:

- an authoring contract an agent can write from conversation
- a deterministic runtime that executes and resumes those workflows reliably

The first release should support:
- parsing and validating workflow files
- running `cli` steps
- pausing on `await_event`
- resuming from persisted state
- returning stable JSON envelopes
- local durable persistence
- deterministic control flow with a very small expression model
- a minimal authoring surface through `guide`, schema docs, and examples

## Scope for phase 1

### Included

- `run`
- `resume`
- `status`
- `inspect`
- `validate`
- `guide`
- `init`
- `cancel`
- `cli` step
- `await_event` step
- `end` step
- minimal transition handling
- SQLite-backed local state store
- JSON Schema validation
- structured error model
- stable exit codes
- console entry point `cpf`

### Excluded

- `api`
- `workflow` subflows
- `foreach`
- `parallel`
- locking
- retry strategies beyond a simple built-in retry
- advanced artifact store
- TUI
- remote execution

## Finalized implementation stack

- CPython 3.13+ with `.python-version` pinned to 3.14 for day-to-day development
- `uv` for dependency management, locking, virtualenv management, build, and publish
- `uv_build` as the package build backend
- Typer for the CLI surface and Rich for human-oriented rendering
- `pydantic` v2 for runtime models, envelopes, and persisted records
- `jsonschema` for workflow, input, and event validation against the bundled schemas
- `PyYAML` with safe loaders for workflow parsing
- standard library `subprocess` for `cli` steps
- standard library `sqlite3` for run metadata, checkpoints, and event history
- filesystem artifact directories under `~/.checkpointflow/runs/<run_id>/`
- Ruff, mypy, pytest, and pytest-cov as the required quality toolchain

## Development method

Phase 1 should be built with strict TDD:

- write the failing test first
- implement the smallest change that makes it pass
- refactor only with a green test suite
- add regression tests for every bug before fixing it

The preferred order is unit test first, then CLI or end-to-end coverage when the behavior boundary is stable.

## Repository structure

```text
src/
  checkpointflow/
    __init__.py
    cli.py
    __main__.py
    engine/
      runner.py
      resume.py
      evaluator.py
      steps/
        cli_step.py
        await_event_step.py
        end_step.py
    models/
      envelope.py
      workflow.py
      state.py
      errors.py
    persistence/
      db.py
      queries.py
      artifacts.py
    py.typed
schemas/
  checkpointflow.schema.json
  checkpointflow-run-envelope.schema.json
tests/
pyproject.toml
uv.lock
```

The package should expose `cpf` as the primary console script.
It should be framed as a local toolchain for authoring, validating, and executing checkpointflows.

Workflow files are path-agnostic and may live anywhere. Runtime state should default to a user-scoped home-directory location instead of a directory relative to the workflow file.

## Core runtime flow

### `run`

1. parse workflow file
2. validate workflow document
3. load and validate input JSON
4. create run record
5. execute from first step
6. for each step:
   - evaluate `if` condition if present
   - run step handler
   - persist event(s)
   - persist outputs
   - transition to next step
7. if `await_event` is reached:
   - persist checkpoint
   - emit waiting envelope
   - exit with code `40`
8. if `end` is reached:
   - emit completed envelope
   - exit with code `0`

### `resume`

1. load run record
2. verify run is in `waiting`
3. verify incoming event name matches expected event
4. validate event JSON against `input_schema`
5. append event history record
6. update current state
7. continue execution from transition target
8. emit final or waiting envelope

## Minimal state store

Suggested layout:

```text
~/.checkpointflow/
  runs.db
  runs/
    <run_id>/
      artifacts/
      stdout/
      stderr/
```

SQLite should be the source of truth for run metadata because `status`, `inspect`, `resume`, and future `list` or `gc` commands benefit from transactional updates and indexed queries. Large process artifacts should remain on disk, referenced from the database.

The workflow path should be stored as metadata in the run record, but persistence location must not depend on where the workflow file lives.

### Required tables

- `runs`
- `events`
- `step_results`
- `artifacts`

### `runs` record

Should contain:
- `run_id`
- `workflow_id`
- `workflow_version`
- `workflow_hash`
- `status`
- `current_step_id`
- `expected_event_name` when waiting
- `expected_event_schema` when waiting
- `inputs_json`
- `step_outputs_json`
- `created_at`
- `updated_at`

## Expression evaluator

Keep it intentionally tiny in v1.

Supported:
- path lookup from `inputs`
- path lookup from `steps.<id>.outputs`
- path lookup from `event`
- equality and inequality
- boolean `and` / `or`

Avoid:
- arbitrary Python evaluation
- file access
- shell execution
- network access

## Step handler contracts

### `cli`

Input:
- step definition
- resolved command string
- runtime context

Output:
- exit code
- parsed stdout JSON if possible
- raw stdout/stderr references
- validated outputs if declared

### `await_event`

Input:
- step definition
- runtime context

Output:
- no side effect beyond persisted checkpoint
- waiting envelope payload
- expected event metadata stored in run state

### `end`

Input:
- step definition
- runtime context

Output:
- final result object
- completed state

## Testing strategy

The test loop for every milestone should be red, green, refactor.

### Unit tests

- workflow parsing
- schema validation
- expression evaluation
- step output validation
- waiting envelope generation
- resume validation
- error envelope generation

### Integration tests

- run simple `cli -> end`
- run `cli -> await_event -> resume -> cli -> end`
- invalid input rejected before execution
- invalid resume event rejected
- step output schema mismatch fails correctly

Recommended first fixtures:
- docs publish workflow with human approval
- repo task with an agent decision step and later resume
- mixed human-agent workflow generated from a conversation transcript

### TDD execution rules

- Start each milestone by naming the next externally visible behavior and writing the failing test for it.
- Keep tests focused on stable contracts such as envelopes, exit codes, and persisted state transitions.
- When a bug is found, first capture it as a regression test at the narrowest useful level.
- Do not merge behavior that only exists in manual testing.

## First-class invariants

These must be true from the first implementation:

1. stdout is always machine-readable JSON
2. wait/resume is explicit and durable
3. no continuation depends on chat history
4. exit code `40` always means waiting, not failure
5. every failure has a stable error code
6. resuming a non-waiting run fails clearly
7. event input is validated before resuming

## Open design questions worth deferring

- subflow trace model
- locks
- remote artifact references
- long-running background tasks
- pluggable step handlers
- visualization

Do not solve these in phase 1.

## Recommended milestone order

### Milestone 1
- models
- workflow schema
- envelope schema
- `cpf validate`
- tests first for schema loading, validation success, and validation failure envelopes

### Milestone 2
- `cpf run`
- `cli`
- `end`
- SQLite persistence layer
- tests first for run creation, step execution, and completed envelopes

### Milestone 3
- `await_event`
- `cpf resume`
- `cpf status`
- `cpf inspect`
- tests first for waiting envelopes, resume validation, and status queries

### Milestone 4
- `cpf guide`
- example workflows
- close remaining coverage gaps and add regression tests from implementation learnings

## Acceptance criteria

Phase 1 is successful when a calling agent can:

1. turn a conversation into a valid checkpointflow document
2. validate that document through `cpf`
3. start the workflow through `cpf`
4. receive a structured waiting envelope
5. ask a user or agent for the required input
6. resume with that input
7. reach a final completed envelope

without any hidden conversational dependency.
