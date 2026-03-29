# checkpointflow

Deterministic, resumable workflows for agents, operators, and shells.

`checkpointflow` lets you define a workflow as a portable state machine in YAML, validate it before execution, run it through a stable CLI, pause for explicit external input, and resume later without relying on hidden chat history or process-local state.

It is built for workflows that mix:

- local CLI steps
- structured branching
- human approval
- bounded agent judgment
- durable handoff across shells, tools, and operators

## Why checkpointflow

Most agent workflows break down in the same places:

- important state lives only in a chat thread
- pause and resume are implicit instead of modeled
- outputs are hard to validate before taking the next step
- another agent or operator cannot reliably continue the work

`checkpointflow` solves that by making the workflow contract explicit:

- workflows are written as versioned YAML documents
- inputs, outputs, and resume events are validated with JSON Schema
- stdout returns stable machine-readable JSON envelopes
- waiting is explicit and durable through `await_event`
- state is persisted under `~/.checkpointflow/` by default
- workflow files can live anywhere on disk

## What You Get

- A narrow, predictable runtime contract that is easy for agents to drive.
- Stable CLI commands for validate, run, resume, inspect, status, cancel, guide, and gui.
- Explicit pause/resume semantics instead of hidden conversational continuation.
- Deterministic control flow driven by persisted inputs and step outputs.
- A default user-scoped state store at `~/.checkpointflow/`.
- A workflow format that is simple enough to derive from human-agent conversation.

## Installation

Install with `uv`:

```bash
uv tool install checkpointflow
```

Then verify the CLI is available:

```bash
cpf --help
cpf guide
```

If you want to use it inside an existing Python project:

```bash
uv add checkpointflow
```

## Quick Start

Create a workflow file anywhere you want, for example `workflow.yaml`:

```yaml
schema_version: checkpointflow/v1
workflow:
  id: publish_confluence_change
  name: Publish Confluence change
  version: 1.0.0
  inputs:
    type: object
    required: [page_id, source_file]
    properties:
      page_id:
        type: string
      source_file:
        type: string

  steps:
    - id: plan
      kind: cli
      command: confpub plan --page-id ${inputs.page_id} --file ${inputs.source_file} --format json
      outputs:
        type: object
        required: [plan_file, summary]
        properties:
          plan_file: { type: string }
          summary: { type: string }

    - id: approval
      kind: await_event
      audience: user
      event_name: change_approval
      prompt: Review the proposed page update and approve or reject it.
      input_schema:
        type: object
        required: [decision]
        properties:
          decision:
            type: string
            enum: [approve, reject]
          comment:
            type: string
      transitions:
        - when: ${event.decision == "approve"}
          next: apply
        - when: ${event.decision == "reject"}
          next: rejected

    - id: apply
      kind: cli
      command: confpub apply --plan ${steps.plan.outputs.plan_file} --format json
      outputs:
        type: object
        required: [page_url]
        properties:
          page_url: { type: string }

    - id: rejected
      kind: end
      result:
        status: rejected

  outputs:
    type: object
    properties:
      page_url:
        from: steps.apply.outputs.page_url
```

Create an input file:

```json
{
  "page_id": "123456",
  "source_file": "docs/architecture.md"
}
```

Validate the workflow:

```bash
cpf validate -f workflow.yaml
```

Run it:

```bash
cpf run -f workflow.yaml --input @input.json
```

If the workflow reaches a wait point, `checkpointflow` exits with code `40` and prints a waiting envelope on stdout:

```json
{
  "schema_version": "checkpointflow-run/v1",
  "ok": true,
  "command": "run",
  "status": "waiting",
  "exit_code": 40,
  "run_id": "01JQEXAMPLE00000000000002",
  "current_step_id": "approval",
  "wait": {
    "kind": "external_event",
    "audience": "user",
    "event_name": "change_approval",
    "prompt": "Review the proposed page update and approve or reject it.",
    "input_schema": {
      "type": "object",
      "required": ["decision"],
      "properties": {
        "decision": {
          "type": "string",
          "enum": ["approve", "reject"]
        },
        "comment": {
          "type": "string"
        }
      }
    },
    "instructions": [
      "Ask the intended audience for input using the prompt.",
      "Collect JSON that matches input_schema.",
      "Resume with the provided run_id and event_name."
    ],
    "resume": {
      "command": "cpf resume --run-id 01JQEXAMPLE00000000000002 --event change_approval --input @response.json"
    }
  }
}
```

Resume with explicit input:

```bash
cpf resume --run-id 01JQEXAMPLE00000000000002 --event change_approval --input @response.json
```

## Core Ideas

### Explicit pause and resume

`checkpointflow` uses a single pause primitive:

- `await_event`

That same primitive covers:

- user approval
- agent decision
- callback from another system
- manual operator continuation

This keeps the runtime small and the resume contract uniform.

### Deterministic orchestration

Control flow is driven by persisted workflow inputs, validated event payloads, and step outputs. The orchestrator does not depend on hidden prompt state, wall-clock reads during evaluation, or direct network results inside expressions.

### Agent-agnostic execution

A workflow can be driven by:

- Codex
- Claude Code
- GitHub Copilot agents
- CI jobs
- shell scripts
- a human operator

The workflow remains the same because the runtime contract remains the same.

## Stable CLI Surface

```bash
cpf init
cpf guide
cpf validate -f workflow.yaml
cpf run -f workflow.yaml --input @input.json
cpf resume --run-id <run_id> --event <event_name> --input @event.json
cpf status --run-id <run_id>
cpf inspect --run-id <run_id>
cpf cancel --run-id <run_id> --reason "..."
cpf gui
```

## Workflow Model

The runtime is intentionally opinionated.

The core step kinds are:

- `cli` — run a shell command
- `await_event` — pause for external input
- `end` — terminate with a result

Additional step kinds for composition and control flow:

- `api` — HTTP request with JSON response capture
- `switch` — conditional branching
- `foreach` — iterate over a list
- `parallel` — concurrent branch execution
- `workflow` — invoke a sub-workflow

See `cpf guide` for full documentation of each step kind.

## Storage Model

Workflow location and runtime state are separate concerns.

- Workflow files can live anywhere on disk.
- Runtime state defaults to `~/.checkpointflow/`.
- Run metadata lives in `~/.checkpointflow/runs.db`.
- Per-run artifacts live under `~/.checkpointflow/runs/<run_id>/`.
- The workflow source path is recorded as metadata, but it does not determine where state is stored.

This makes workflows easy to keep in repos, temp directories, shared folders, or generated output locations without coupling them to runtime storage.

## Exit Codes

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

`40` is not a failure. It means the workflow is paused and ready to be resumed with an explicit event payload.

## Who It Is For

`checkpointflow` is a good fit if you want to:

- turn a conversation into a durable workflow file
- run mixed human-agent workflows without hidden continuation
- encode operational runbooks that can be resumed later
- keep the reliable parts of an agent workflow outside the prompt
- hand work from one agent or operator to another safely

It is not trying to be a general-purpose programming language or a heavyweight distributed orchestration platform.

## Documentation

- [Workflow Schema](./schemas/checkpointflow.schema.json)
- [Run Envelope Schema](./schemas/checkpointflow-run-envelope.schema.json)
- [Example Workflow](./examples/publish-confluence-change.yaml)
- [Contributing](./CONTRIBUTING.md)

## Development

This project is developed with strict TDD and uses `uv` as the package manager.

```bash
uv sync --group dev
uv run python scripts/install_git_hooks.py
uv run pytest
uv run ruff check .
uv run mypy
```

GitHub Actions enforces the same quality gate in CI:

- `uv lock --check`
- `ruff format --check`
- `ruff check`
- `mypy`
- cross-platform `pytest`
- `uv build` plus a built-wheel smoke test

## License

Private repository.
