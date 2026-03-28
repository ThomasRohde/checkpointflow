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
- file-based persistence
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
- file-based state store
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

## Suggested implementation stack

- Python 3.12+
- `pydantic` for runtime models
- `jsonschema` for workflow/input/event validation
- `PyYAML` or `ruamel.yaml` for parsing
- standard library `subprocess` for `cli` steps
- file-based run store under `.runs/`

## Repository structure

```text
checkpointflow/
  cli.py
  engine/
    runner.py
    resume.py
    evaluator.py
    state.py
    steps/
      cli_step.py
      await_event_step.py
      end_step.py
  models/
    envelope.py
    workflow.py
    state.py
    errors.py
  schemas/
    checkpointflow.schema.json
    checkpointflow-run-envelope.schema.json
  guide/
    guide.md
  tests/
pyproject.toml
```

The package should expose `cpf` as the primary console script.
It should be framed as a local toolchain for authoring, validating, and executing checkpointflows.

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
.runs/
  <run_id>/
    run.json
    events.jsonl
    steps/
      <step_id>.json
    artifacts/
    stdout/
    stderr/
```

### `run.json`

Should contain:
- `run_id`
- `workflow_id`
- `workflow_version`
- `workflow_hash`
- `status`
- `current_step_id`
- `expected_event_name` when waiting
- `expected_event_schema` when waiting
- `inputs`
- `step_outputs`
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

### Milestone 2
- `cpf run`
- `cli`
- `end`
- file state store

### Milestone 3
- `await_event`
- `cpf resume`
- `cpf status`
- `cpf inspect`

### Milestone 4
- tests
- `cpf guide`
- example workflows

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
