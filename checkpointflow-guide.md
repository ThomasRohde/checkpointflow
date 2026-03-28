# checkpointflow guide

This file is written as if it were the output backing `cpf guide`.

## What checkpointflow is

`checkpointflow` is a deterministic, resumable, agent-agnostic CLI toolchain for authoring and running reusable workflows.

It is designed for workflows that mix:
- deterministic machine steps
- explicit branching
- pause/resume for user or agent input
- durable execution across restarts and handoffs

Typical use cases:
- turn a conversation into a YAML workflow that stitches together actions and interaction points
- encode existing runbooks that mix CLIs, APIs, human review, and agent judgment
- pause and resume long-lived workflows across agents or operators without hidden context

The package has two jobs:
- help an agent or operator author a valid checkpointflow document
- execute that document through a deterministic runtime contract

The runtime core can stay narrow even when the authoring surface is broad.

## Authoring model

A common loop is:

1. a user and agent work through a task in conversation
2. the agent extracts inputs, steps, interactions, and transitions
3. the agent writes a `checkpointflow/v1` YAML file
4. `cpf validate` checks the document against the schema
5. `cpf run` executes it and emits structured envelopes
6. `cpf resume` continues the run when external input arrives

Workflow files are location-independent. They can live anywhere on disk, and the CLI should operate on the explicit file path you pass in.

Runtime state is separate from workflow location. By default, checkpointflow stores run state under `~/.checkpointflow/`.

## Workflow file

Top-level structure:

```yaml
schema_version: checkpointflow/v1
workflow:
  id: my_workflow
  name: My workflow
  version: 0.1.0
  inputs: { ... }
  steps: [ ... ]
  outputs: { ... }
```

## Supported step kinds

### cli

Runs a shell/CLI command.

Required:
- `id`
- `kind: cli`
- `command`

Recommended:
- `outputs`
- `timeout_seconds`
- `retry`
- `shell`

### api

Runs an HTTP call.

Required:
- `id`
- `kind: api`
- `method`
- `url`

### workflow

Invokes a subflow.

Required:
- `id`
- `kind: workflow`
- `workflow_ref`

### await_event

Pauses and waits for explicit external input.

Required:
- `id`
- `kind: await_event`
- `audience`
- `event_name`
- `input_schema`

### switch

Branches using a small declarative condition set.

Required:
- `id`
- `kind: switch`
- `cases`

### foreach

Iterates over a collection.

Required:
- `id`
- `kind: foreach`
- `items`
- `body` or `workflow_ref`

### parallel

Runs branches concurrently.

Required:
- `id`
- `kind: parallel`
- `branches`

### end

Terminates the run with an explicit result.

Required:
- `id`
- `kind: end`

## Why `await_event` exists

The runtime deliberately treats user approval, agent judgment, and system callbacks as the same primitive:
- `kind: await_event`

Examples:

User approval:

```yaml
- id: approval
  kind: await_event
  audience: user
  event_name: approve_change
  input_schema:
    type: object
    required: [decision]
    properties:
      decision:
        type: string
        enum: [approve, reject]
```

Agent decision:

```yaml
- id: choose_strategy
  kind: await_event
  audience: agent
  event_name: strategy_selected
  input_schema:
    type: object
    required: [strategy]
    properties:
      strategy:
        type: string
        enum: [safe, fast, cheap]
```

This keeps the runtime small and the pause/resume contract uniform.

## CLI commands

Authoring and documentation:

```bash
cpf init
cpf validate -f workflow.yaml
cpf guide
```

Execution and inspection:

```bash
cpf run -f workflow.yaml --input @input.json
cpf resume --run-id <run_id> --event <event_name> --input @event.json
cpf status --run-id <run_id>
cpf inspect --run-id <run_id>
cpf logs --run-id <run_id>
cpf cancel --run-id <run_id> --reason "..."
```

The `-f/--file` path may point anywhere. Running a workflow from `/tmp`, a repo directory, or a shared docs folder must not change where run state is persisted.

## JSON result envelope

All commands return a stable JSON envelope on stdout.

Example:

```json
{
  "schema_version": "checkpointflow-run/v1",
  "request_id": "01JQ...",
  "ok": true,
  "command": "run",
  "status": "waiting",
  "run_id": "01JQ...",
  "current_step_id": "approval",
  "result": {}
}
```

## Waiting behavior

When execution reaches `await_event`, the CLI:
- persists a checkpoint
- exits with code `40`
- writes a waiting envelope to stdout

By default, the checkpoint and run metadata are written under `~/.checkpointflow/`, not next to the workflow file.

Example:

```json
{
  "schema_version": "checkpointflow-run/v1",
  "ok": true,
  "command": "run",
  "status": "waiting",
  "exit_code": 40,
  "run_id": "01JQ...",
  "checkpoint_id": "01JQ...",
  "current_step_id": "approval",
  "wait": {
    "kind": "external_event",
    "audience": "user",
    "event_name": "approve_change",
    "prompt": "Review the change and approve or reject it.",
    "input_schema": {
      "type": "object",
      "required": ["decision"],
      "properties": {
        "decision": {
          "type": "string",
          "enum": ["approve", "reject"]
        }
      }
    },
    "instructions": [
      "Ask the intended audience for input using the prompt.",
      "Collect JSON that matches input_schema.",
      "Resume with the provided run_id and event_name."
    ],
    "resume": {
      "command": "cpf resume --run-id 01JQ... --event approve_change --input @response.json"
    }
  }
}
```

## Exit codes

```text
0   Success
10  Validation error
20  Runtime error
30  Step failed
40  Waiting for external event
50  Cancelled
60  Persistence error
70  Concurrency or lock error
80  Unsupported feature
90  Internal error
```

## Error codes

Suggested stable machine-readable errors:

- `ERR_VALIDATION_WORKFLOW`
- `ERR_VALIDATION_INPUT`
- `ERR_VALIDATION_EVENT_INPUT`
- `ERR_STEP_FAILED`
- `ERR_STEP_OUTPUT_INVALID`
- `ERR_TIMEOUT`
- `ERR_LOCK_CONFLICT`
- `ERR_PERSISTENCE`
- `ERR_UNSUPPORTED_STEP_KIND`
- `ERR_RESUME_EVENT_MISMATCH`
- `ERR_RUN_NOT_WAITING`
- `ERR_RUN_NOT_FOUND`

## Compatibility policy

- `schema_version` is mandatory
- breaking changes require a new major version
- unknown optional fields may be ignored with warnings
- unknown step kinds must fail clearly

## Example run loop

```bash
cpf run -f publish.yaml --input @input.json
```

If the workflow pauses, capture the waiting envelope, gather the requested input, then resume:

```bash
cpf resume --run-id 01JQ... --event approve_change --input @response.json
```
