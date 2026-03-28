# checkpointflow — CLI Toolchain for Authoring and Running Agent Workflows

Version: 0.1.0  
Status: Draft PRD / Technical Specification

## 1. Purpose

`checkpointflow` is a CLI package and workflow schema for authoring, validating, and running reusable agent workflows as deterministic, resumable state machines.

The central idea is simple:

- the **CLI package** is the local toolchain for authoring, validating, inspecting, and executing workflows
- the **runtime** owns execution, state, and pause/resume semantics
- the **agent** can synthesize workflow YAML from conversation and drive the CLI
- the **workflow** is portable across agents because it never depends on hidden conversational state

This is intended for workflows that are partly deterministic and partly interactive, where an agent may need to:

- run commands
- call APIs
- branch based on structured results
- pause for user approval
- pause for bounded agent judgment
- resume later with explicit structured input
- hand work to another agent or operator without losing state
- turn an exploratory conversation into a durable workflow spec

Primary workflows to support:

- compile a conversation into a YAML workflow that stitches together actions and interaction points
- execute mixed human-agent workflows without hidden conversational continuation
- encode reusable operational runbooks that can be replayed, inspected, and resumed

The goal is not to build a general workflow engine. The goal is to build a reliable CLI toolchain and runtime contract for workflows that agents can author and operators can trust.

## 2. Non-goals

`checkpointflow` is not intended to be:

- a full replacement for BPMN, Temporal, Argo, or cloud workflow engines
- a general-purpose programming language
- a conversational memory system
- a hidden prompt execution framework
- a general automation platform for every workflow in the company
- a workflow engine that embeds arbitrary scripting in control flow

## 3. Core thesis

Agent workflows should be portable state machines, not prompt blobs.

A workflow should:

- declare inputs, outputs, steps, transitions, and wait points
- execute through a stable CLI contract
- persist enough state to survive process failure and agent handoff
- expose structured instructions to any calling agent when it needs outside input

## 4. Design principles

### 4.1 Agent agnostic

The same workflow must be runnable from:

- Codex
- Claude Code
- GitHub Copilot agents
- a shell script
- a TUI
- a human operator

The runtime must never assume a specific model vendor, UI, or chat product.

### 4.2 Deterministic orchestration

Workflow control flow must be replay-safe.

The orchestrator must not depend on:

- hidden model state
- wall-clock reads during control evaluation
- randomness during control evaluation
- network calls during control evaluation
- environment inspection during control evaluation

Nondeterministic work belongs in effectful steps.

### 4.3 Explicit pause/resume

Any external input is modeled as an event.

This includes:

- human approval
- agent decision
- external callback
- manual operator continuation

### 4.4 Durable execution

Every run must be restartable.

A run must survive:

- CLI process exit
- agent crash
- machine restart
- delayed continuation
- agent handoff

### 4.5 Strong machine contracts

All commands must return a stable JSON envelope.

All wait points must return enough information for another process to gather input and resume execution without hidden context.

### 4.6 Narrow over broad

The runtime semantics and expression language must remain deliberately small even if the authoring surface is broader.

### 4.7 Conversation-compilable by design

The format should be simple enough that an agent can reliably derive a valid document from conversation.

That implies:

- explicit step kinds instead of hidden prompt logic
- typed inputs and event schemas
- clear transitions and resume points
- enough structure for validation before execution

## 5. Conceptual model

A workflow run is a persistent state machine.

Authoring happens before execution:

1. a human and agent discuss a task
2. the agent extracts inputs, actions, pauses, and transitions
3. the agent emits a `checkpointflow/v1` document
4. the CLI validates the document
5. the runtime executes and resumes it

Each run has:

- workflow definition hash
- resolved inputs
- current step pointer
- step outputs
- event history
- artifacts metadata
- status
- checkpoints

The runtime proceeds step by step until it:

- completes successfully
- fails
- is cancelled
- reaches an `await_event` step

When an `await_event` step is reached, execution pauses and the CLI emits a structured waiting envelope telling the caller:

- what input is needed
- who is expected to provide it
- the JSON schema for the input
- how to resume the run

## 6. Unifying pause semantics

The runtime should not have separate primitives like `await_approval` and `await_agent`.

Instead it should have one pause primitive:

- `await_event`

Special cases are represented by metadata, not different control structures.

Examples:

- user approval → `kind: await_event`, `audience: user`
- agent decision → `kind: await_event`, `audience: agent`
- callback from another system → `kind: await_event`, `audience: system`

This keeps the runtime simpler and the pause contract uniform.

## 7. CLI surface

The package should be framed as a workflow authoring and execution toolchain.

### 7.1 Required commands

```bash
cpf init
cpf validate -f workflow.yaml
cpf guide
cpf run -f workflow.yaml --input @input.json
cpf resume --run-id <run_id> --event <event_name> --input @event.json
cpf status --run-id <run_id>
cpf inspect --run-id <run_id>
cpf logs --run-id <run_id>
cpf cancel --run-id <run_id> --reason "..."
```

### 7.2 Optional commands

```bash
cpf list
cpf retry-step --run-id <run_id> --step-id <step_id>
cpf export --run-id <run_id> --format json
cpf gc
```

### 7.3 CLI behavior rules

- stdout is reserved for structured result envelopes
- stderr is reserved for logs and progress
- non-interactive behavior is first-class
- human-readable output modes may exist, but JSON must remain authoritative
- `LLM=true` must force strictly agent-friendly behavior
- the CLI should work well when driven by an agent that is creating or editing workflow YAML

## 8. Exit code taxonomy

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

Exit code `40` is especially important. It does not mean failure. It means the run is paused and waiting.

## 9. Standard output envelope

All commands must emit a consistent JSON envelope.

### 9.1 Envelope shape

```json
{
  "schema_version": "checkpointflow-run/v1",
  "request_id": "01JQ...",
  "ok": true,
  "command": "run",
  "status": "running|waiting|completed|failed|cancelled",
  "run_id": "01JQ...",
  "current_step_id": "approval",
  "result": {}
}
```

### 9.2 Required top-level fields

- `schema_version`
- `request_id`
- `ok`
- `command`
- `status`
- `run_id` when a run exists

### 9.3 Recommended top-level fields

- `workflow_id`
- `workflow_version`
- `current_step_id`
- `started_at`
- `updated_at`
- `warnings`
- `result`
- `error`

## 10. Waiting envelope

When execution pauses, stdout must contain a structured waiting envelope.

### 10.1 Example

```json
{
  "schema_version": "checkpointflow-run/v1",
  "request_id": "01JQ...",
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
    "event_name": "change_approval",
    "prompt": "Review the proposed change and approve or reject it.",
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
      "command": "cpf resume --run-id 01JQ... --event change_approval --input @response.json"
    }
  }
}
```

### 10.2 Required wait fields

- `kind`
- `audience`
- `event_name`
- `input_schema`
- `resume`

### 10.3 Optional wait fields

- `prompt`
- `timeout_at`
- `default_on_timeout`
- `examples`
- `attachments`
- `risk_level`
- `summary`

## 11. Workflow schema

### 11.1 Top-level document

```yaml
schema_version: checkpointflow/v1
workflow:
  id: string
  name: string
  description: string
  version: string
  defaults: {}
  inputs: {}
  steps: []
  outputs: {}
```

### 11.2 Required workflow fields

- `schema_version`
- `workflow.id`
- `workflow.inputs`
- `workflow.steps`

### 11.3 Recommended workflow fields

- `workflow.name`
- `workflow.description`
- `workflow.version`
- `workflow.defaults`
- `workflow.outputs`

## 12. Supported step kinds

The runtime should support a deliberately small step taxonomy.

### 12.1 `cli`

Run a command.

Use for:

- local tools
- shell commands
- repo-local CLIs
- deterministic machine steps whose side effects are encapsulated in the called command

### 12.2 `api`

Call an HTTP operation.

Use when an operation is naturally modeled as an API call rather than a shell command.

### 12.3 `workflow`

Invoke another workflow as a subflow.

### 12.4 `await_event`

Pause and wait for structured external input.

### 12.5 `switch`

Branch based on a small declarative expression.

### 12.6 `foreach`

Iterate over a collection.

### 12.7 `parallel`

Run branches concurrently when explicitly allowed.

### 12.8 `end`

Terminate with an explicit result.

## 13. Step specifications

### 13.1 Common step fields

All step kinds should support the following common fields where relevant:

- `id`
- `kind`
- `name`
- `description`
- `if`
- `timeout_seconds`
- `retry`
- `risk_level`
- `inputs`
- `outputs`
- `artifacts`
- `on_error`
- `tags`

### 13.2 `cli` step

#### Example

```yaml
- id: plan
  kind: cli
  command: confpub plan --page-id ${inputs.page_id} --file ${inputs.source_file} --format json
  shell: bash
  timeout_seconds: 300
  retry:
    max_attempts: 2
    backoff_seconds: 3
  success:
    exit_codes: [0]
  outputs:
    type: object
    required: [plan_file, summary]
    properties:
      plan_file: { type: string }
      summary: { type: string }
```

#### Required fields

- `id`
- `kind: cli`
- `command`

#### Recommended fields

- `shell`
- `timeout_seconds`
- `success`
- `outputs`
- `retry`

#### Semantics

- command execution is effectful
- stdout should preferably be parseable structured JSON
- stderr is diagnostic only
- if `outputs` is declared, the parsed result must validate against it

### 13.3 `api` step

#### Example

```yaml
- id: publish
  kind: api
  method: POST
  url: https://example/api/publish
  headers:
    Authorization: Bearer ${inputs.token}
  body:
    file: ${steps.plan.outputs.plan_file}
  success:
    status_codes: [200, 201]
  outputs:
    type: object
    properties:
      page_url: { type: string }
```

### 13.4 `await_event` step

#### Example

```yaml
- id: approval
  kind: await_event
  audience: user
  event_name: change_approval
  prompt: Review the proposed change and approve or reject it.
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
```

#### Required fields

- `id`
- `kind: await_event`
- `audience`
- `event_name`
- `input_schema`

#### Recommended fields

- `prompt`
- `transitions`
- `timeout_seconds`
- `on_timeout`
- `risk_level`
- `summary`

#### Semantics

- reaching this step persists a checkpoint
- the CLI exits with code `40`
- the runtime emits a waiting envelope
- the run resumes only through `cpf resume`

### 13.5 `workflow` step

#### Example

```yaml
- id: run_subflow
  kind: workflow
  workflow_ref: reusable/publish-plan.yaml
  inputs:
    page_id: ${inputs.page_id}
```

#### Semantics

- subflow execution creates nested traceability
- subflow outputs become available to parent workflow
- parent workflow may choose fail-fast or fail-capture behavior

### 13.6 `switch` step

#### Example

```yaml
- id: choose_mode
  kind: switch
  cases:
    - when: ${inputs.mode == "safe"}
      next: safe_path
    - when: ${inputs.mode == "fast"}
      next: fast_path
  default: safe_path
```

### 13.7 `parallel` step

#### Example

```yaml
- id: gather
  kind: parallel
  branches:
    - start_at: fetch_a
    - start_at: fetch_b
```

#### Semantics

- parallelism must be explicit
- shared-resource conflicts should be prevented with declared locks

### 13.8 `end` step

#### Example

```yaml
- id: rejected
  kind: end
  result:
    status: rejected
```

## 14. Expression language

Keep expressions intentionally tiny.

Allowed examples:

- `${inputs.page_id}`
- `${steps.plan.outputs.plan_file}`
- `${event.decision == "approve"}`

Disallowed at v1:

- arbitrary scripting
- filesystem reads in expressions
- network calls in expressions
- random values
- hidden state lookups

## 15. Inputs and outputs

All workflow inputs and step outputs should be typed with JSON Schema-compatible structures.

### Requirements

- workflow inputs must be validated before execution begins
- event inputs must be validated before resume is accepted
- step outputs must be validated when an output schema is declared

## 16. State model

### 16.1 Run states

A run may be in one of these states:

- `created`
- `running`
- `waiting`
- `completed`
- `failed`
- `cancelled`

### 16.2 Step states

A step may be in one of these states:

- `pending`
- `running`
- `waiting`
- `completed`
- `failed`
- `skipped`
- `cancelled`

### 16.3 Event history

The runtime must append a durable event record for important events such as:

- run created
- step started
- step completed
- step failed
- wait entered
- event received
- run resumed
- run cancelled
- run completed

## 17. Persistence model

A simple file-based reference implementation is acceptable.

### Suggested layout

```text
.runs/
  <run_id>/
    run.json
    events.jsonl
    steps/
    artifacts/
    stdout/
    stderr/
```

### Minimum persisted data

- workflow hash
- workflow id and version
- resolved inputs
- current status
- current step
- completed step outputs
- event history
- checkpoints
- timestamps
- lock metadata if used

SQLite may be added later for indexing and search.

## 18. Determinism rules

The orchestrator must behave as if it were replayable.

### Must not influence control flow

- random values
- current time reads not captured as events
- mutable environment inspection
- direct network results in expressions
- implicit chat history

### Acceptable pattern

- effectful step runs
- its structured output is persisted
- subsequent control flow uses persisted output only

## 19. Idempotency and retries

Idempotency must be first-class for effectful steps.

### Recommended step fields

- `idempotency_key`
- `retry.max_attempts`
- `retry.backoff_seconds`
- `retry.strategy`

### Rules

- retries must be explicit
- resume must not repeat already-committed work unless policy allows it
- effectful commands should accept external idempotency keys where possible

## 20. Timeouts and timers

The runtime should support:

- step timeout
- wait timeout
- optional default transitions on timeout

Example:

```yaml
- id: approval
  kind: await_event
  audience: user
  event_name: change_approval
  timeout_seconds: 86400
  on_timeout:
    next: timed_out
```

## 21. Concurrency and locking

If workflows touch shared resources, locking must be available.

### Recommended model

A step may declare a lock key:

```yaml
lock:
  key: confluence:page:${inputs.page_id}
  mode: exclusive
```

### Rules

- lock acquisition must be explicit
- lock conflicts should return stable machine-readable errors
- lock metadata should be inspectable

## 22. Artifacts

Artifacts are named files or references produced by steps.

Examples:

- generated markdown
- diff files
- screenshots
- plan files
- review bundles

### Artifact metadata should include

- logical name
- path or URI
- media type
- producer step id
- checksum if practical

## 23. Human and agent interaction model

The workflow never directly chats with a user.

Instead:

1. runtime reaches `await_event`
2. runtime emits structured waiting envelope
3. agent or operator gathers input externally
4. caller resumes workflow with explicit JSON input

This keeps the runtime portable across agent environments.

### `await_agent`

There should be no separate core runtime primitive for `await_agent`.

Instead use:

```yaml
kind: await_event
audience: agent
```

This means the runtime is asking the calling agent to perform bounded work and return structured input.

## 24. Safety and mutation controls

For mutation-heavy workflows, the runtime should encourage safe defaults.

### Recommended controls

- `dry_run_supported`
- `risk_level`
- `verify` assertions
- pre-apply preview artifacts
- explicit approval gates for medium/high risk mutations

## 25. Error model

Errors must be structured, stable, and machine-readable.

### Envelope

```json
{
  "schema_version": "checkpointflow-run/v1",
  "ok": false,
  "command": "run",
  "status": "failed",
  "error": {
    "code": "ERR_STEP_OUTPUT_INVALID",
    "message": "Step output did not match declared schema.",
    "step_id": "plan",
    "details": {}
  }
}
```

### Suggested error codes

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

## 26. Guide command

The CLI must provide a built-in `guide` command.

It should document:

- workflow file structure
- supported step kinds
- input and output schema rules
- stdout envelope schema
- wait/resume contract
- exit codes
- error taxonomy
- examples
- compatibility guarantees

## 27. Compatibility policy

`checkpointflow` should include explicit compatibility semantics.

### Required policy

- `schema_version` is mandatory
- breaking changes require a new major schema version
- unknown optional fields may be ignored with warnings
- unknown step kinds must fail clearly

## 28. Example workflow

```yaml
schema_version: checkpointflow/v1
workflow:
  id: publish_confluence_change
  name: Publish Confluence change
  description: Plan, approve, and apply a page update.
  version: 0.1.0
  defaults:
    shell: bash
    timeout_seconds: 300
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
        required: [plan_file, summary, risk_level]
        properties:
          plan_file: { type: string }
          summary: { type: string }
          risk_level:
            type: string
            enum: [low, medium, high]

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

## 29. Reference implementation guidance

A first implementation should:

- use YAML for workflow files
- use JSON Schema validation
- store runs in files or SQLite
- expose exact JSON envelopes on stdout
- keep the expression evaluator minimal
- treat `await_event` as the primary pause primitive

Avoid in v1:

- arbitrary embedded code
- dynamic plugin execution in control flow
- giant templating language
- hidden conversational continuation state

## 30. Why this matters

This design provides a practical middle ground between brittle prompt-only agent runbooks and heavyweight workflow platforms.

It gives agent systems a way to externalize the reliable parts of a workflow into a deterministic, inspectable, resumable contract while leaving bounded judgment to the agent where appropriate.

## 31. Implementation priorities

### Phase 1

- workflow parser
- schema validator
- `run`, `resume`, `status`, `validate`, `guide`
- `cli`, `await_event`, `end`
- JSON envelopes
- file-based persistence

### Phase 2

- `workflow` subflows
- `switch`
- retries
- timeouts
- locks
- artifacts metadata

### Phase 3

- `api`
- `foreach`
- `parallel`
- SQLite index
- visualization / TUI support

## 32. Final recommendation

Build `checkpointflow` as a CLI package with a narrow, opinionated runtime core for deterministic agent workflows.

Do not try to become a universal orchestration platform.

Keep the contracts crisp:

- deterministic orchestration
- effectful steps
- explicit waits
- durable state
- structured resume instructions
- agent-agnostic operation
- authoring-friendly structure

That is the shape most likely to be both useful and maintainable.
