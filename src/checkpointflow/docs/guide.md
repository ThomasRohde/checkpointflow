# checkpointflow guide

## What checkpointflow is

checkpointflow is a deterministic, resumable, agent-agnostic CLI toolchain for authoring and running workflows defined in YAML.

It is designed for workflows that mix:
- deterministic machine steps (CLI commands)
- explicit pause/resume for user or agent input
- durable execution across restarts and handoffs

Typical use cases:
- turn a conversation into a YAML workflow that stitches together actions and interaction points
- encode existing runbooks that mix CLIs, human review, and agent judgment
- pause and resume long-lived workflows across agents or operators without hidden context

## Authoring model

A common loop is:

1. a user and agent work through a task in conversation
2. the agent extracts inputs, steps, interactions, and transitions
3. the agent writes a `checkpointflow/v1` YAML file
4. `cpf validate` checks the document against the schema
5. `cpf run` executes it and emits structured envelopes
6. `cpf resume` continues the run when external input arrives

Workflow files are location-independent. They can live anywhere on disk.

Runtime state is separate from workflow location. By default, checkpointflow stores run state under `~/.checkpointflow/`.

## Workflow file

Top-level structure:

```yaml
schema_version: checkpointflow/v1
workflow:
  id: my_workflow
  name: My workflow
  version: 0.1.0
  defaults:
    shell: bash
  inputs: { ... }
  steps: [ ... ]
  outputs: { ... }
```

The optional `defaults` object sets workflow-level defaults. Currently supported: `defaults.shell` sets the shell for all CLI steps (can be overridden per step).

Steps execute sequentially. Each step must have a unique `id`. If no `end` step is present, the workflow completes implicitly after the last step with no result.

## Step kinds

### cli (supported)

Runs a shell command. The command string supports `${inputs.x}` and `${steps.<id>.outputs.x}` interpolation.

Required fields: `id`, `kind: cli`, `command`

Optional fields:
- `cwd` — working directory for the command. Supports `${inputs.x}` interpolation. If omitted, runs in the directory where `cpf` was invoked.
- `shell` — shell to use. Supported values: `bash`, `sh`, `powershell`, `pwsh`, `cmd`. Default: system shell. Can also be set at the workflow level via `defaults.shell`.
- `outputs` — JSON Schema for expected stdout JSON. If defined, stdout must be valid JSON matching this schema or the step fails.
- `timeout_seconds` — kill the process after this many seconds
- `retry` — retry configuration with `max_attempts`, `backoff_seconds`, `strategy` (`fixed` or `exponential`). Note: retry is accepted by the schema but not yet enforced by the runtime.
- `if` — expression that must evaluate to true for the step to run (e.g., `inputs.mode == "full"`)

```yaml
- id: plan
  kind: cli
  cwd: ${inputs.project_dir}
  command: my-tool plan --id ${inputs.page_id} --format json
  timeout_seconds: 300
  outputs:
    type: object
    required: [plan_file]
    properties:
      plan_file: { type: string }
```

### await_event (supported)

Pauses execution and waits for explicit external input. The CLI exits with code 40 and returns a waiting envelope containing everything needed to resume.

Required fields: `id`, `kind: await_event`, `audience`, `event_name`, `input_schema`

Optional fields:
- `prompt` — human-readable description of what input is needed (included in the waiting envelope when present)
- `summary` — short summary for display
- `transitions` — list of `{when, next}` rules evaluated against the event data on resume. If transitions are defined, the first matching `when` condition determines which step to jump to. If no transitions are defined, execution continues to the next step in the array.

```yaml
- id: approval
  kind: await_event
  audience: user
  event_name: change_approval
  prompt: Approve or reject the proposed change.
  input_schema:
    type: object
    required: [decision]
    properties:
      decision:
        type: string
        enum: [approve, reject]
  transitions:
    - when: ${event.decision == "approve"}
      next: apply
    - when: ${event.decision == "reject"}
      next: rejected
```

### end (supported)

Terminates the run with an explicit result. The result can be any JSON value.

Required fields: `id`, `kind: end`

Optional fields:
- `result` — the value to return in the completed envelope

```yaml
- id: done
  kind: end
  result:
    status: completed
    page_url: ${steps.apply.outputs.page_url}
```

### Planned step kinds (not yet supported at runtime)

The following step kinds are defined in the schema but not yet implemented. They will return exit code 80 (`ERR_UNSUPPORTED_STEP`) if encountered during `cpf run`. The `api` and `workflow` kinds pass `cpf validate`; the others may require exact schema compliance.

- **api** — HTTP call. Required: `method`, `url`.
- **workflow** — subflow invocation. Required: `workflow_ref`.
- **switch** — conditional branching. Required: `cases` (array of `{when, next}`).
- **foreach** — iteration. Required: `items`, plus `body` or `workflow_ref`.
- **parallel** — concurrent branches. Required: `branches` (array of `{start_at}`).

## Common step fields

All step kinds accept these optional fields:

- `name` — human-readable step name
- `description` — longer description
- `if` — conditional expression; step is skipped when false
- `timeout_seconds` — maximum execution time
- `risk_level` — `low`, `medium`, or `high`
- `retry` — `{max_attempts, backoff_seconds, strategy}`
- `outputs` — JSON Schema for step output validation
- `tags` — list of string tags

## Expressions

Expressions appear in `command` strings, `if` conditions, and transition `when` clauses.

Syntax: `${<expression>}`

Path lookups:
- `inputs.<field>` — workflow input values
- `steps.<step_id>.outputs.<field>` — output from a previous step
- `event.<field>` — event data (only available in transition `when` clauses after resume)

Comparison operators: `==`, `!=`

Boolean operators: `and`, `or`

Examples:
- `${inputs.page_id}` — interpolated into a command string
- `inputs.mode == "full"` — used in an `if` condition (no `${}` wrapper needed)
- `${event.decision == "approve"}` — used in a transition `when` clause

## CLI commands

Authoring and documentation:

```bash
cpf init                              # scaffold a new workflow YAML file
cpf init --file path/to/workflow.yaml # scaffold at a specific path
cpf validate -f workflow.yaml         # validate against the schema
cpf guide                             # print this guide
```

Execution and inspection:

```bash
cpf run -f workflow.yaml --input @input.json
cpf run -f workflow.yaml --input '{"key": "value"}'
cpf resume --run-id <run_id> --event <event_name> --input @event.json
cpf status --run-id <run_id>
cpf inspect --run-id <run_id>
cpf cancel --run-id <run_id> --reason "..."
```

The `--input` flag accepts either inline JSON or `@path/to/file.json` (reads from file).

The `-f`/`--file` path may point anywhere. Workflow location does not affect where run state is persisted.

Note: `status` and `inspect` return the run's state exit code (e.g., 40 for waiting, 30 for failed), not the query's success code. A successful query of a failed run returns exit code 30.

## JSON result envelope

All commands return a stable JSON envelope on stdout. The envelope always contains:
- `schema_version` — always `"checkpointflow-run/v1"`
- `ok` — `true` on success, `false` on failure
- `command` — the command that was run
- `status` — `completed`, `waiting`, `failed`, `cancelled`, etc.
- `exit_code` — numeric exit code

Success example:

```json
{
  "schema_version": "checkpointflow-run/v1",
  "ok": true,
  "command": "run",
  "status": "completed",
  "exit_code": 0,
  "run_id": "a1b2c3...",
  "workflow_id": "my_workflow",
  "result": { "status": "done" }
}
```

Error example:

```json
{
  "schema_version": "checkpointflow-run/v1",
  "ok": false,
  "command": "run",
  "status": "failed",
  "exit_code": 30,
  "error": {
    "code": "ERR_STEP_FAILED",
    "message": "Step 'deploy' exited with code 1"
  }
}
```

## Waiting behavior

When execution reaches an `await_event` step, the CLI:
- persists the run state to `~/.checkpointflow/`
- exits with code 40
- writes a waiting envelope to stdout

The waiting envelope includes a `wait` block with everything needed to resume:

```json
{
  "schema_version": "checkpointflow-run/v1",
  "ok": true,
  "command": "run",
  "status": "waiting",
  "exit_code": 40,
  "run_id": "a1b2c3...",
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
        "decision": { "type": "string", "enum": ["approve", "reject"] }
      }
    },
    "instructions": [
      "Ask the intended audience for input using the prompt.",
      "Collect JSON that matches input_schema.",
      "Resume with the provided run_id and event_name."
    ],
    "resume": {
      "command": "cpf resume --run-id a1b2c3... --event approve_change --input @response.json"
    }
  }
}
```

Exit code 40 means "waiting for input" — it is not a failure.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 10 | Validation error (workflow, input, or event) |
| 20 | Runtime error |
| 30 | Step failed |
| 40 | Waiting for external event (not a failure) |
| 50 | Cancelled |
| 60 | Persistence error |
| 80 | Unsupported feature (step kind not yet implemented) |
| 90 | Internal error |

## Error codes

Machine-readable error codes in the `error.code` field:

| Code | Meaning |
|------|---------|
| `ERR_VALIDATION_WORKFLOW` | Workflow YAML does not match the schema |
| `ERR_VALIDATION_INPUT` | Input JSON does not match the workflow's input schema |
| `ERR_VALIDATION_EVENT_INPUT` | Resume event JSON does not match the expected schema |
| `ERR_FILE_NOT_FOUND` | Specified file does not exist |
| `ERR_FILE_EXISTS` | File already exists (e.g., `cpf init` without `--force`) |
| `ERR_YAML_PARSE` | YAML syntax error |
| `ERR_STEP_FAILED` | CLI step exited with a non-success code |
| `ERR_STEP_OUTPUT_INVALID` | Step stdout does not match the declared outputs schema |
| `ERR_TIMEOUT` | Step exceeded its timeout |
| `ERR_UNSUPPORTED_STEP` | Step kind is not supported in this version |
| `ERR_DUPLICATE_STEP_ID` | Two or more steps share the same ID |
| `ERR_PERSISTENCE` | Database or file write failed |
| `ERR_RESUME_EVENT_MISMATCH` | Resume event name does not match what the run expects |
| `ERR_RUN_NOT_WAITING` | Attempted to resume or cancel a run that is not in a waiting state |
| `ERR_RUN_NOT_FOUND` | No run exists with the given ID |
| `ERR_INTERNAL` | Unexpected internal error |

## Example run loop

```bash
# Start the workflow
cpf run -f publish.yaml --input @input.json

# If it pauses (exit code 40), gather the requested input and resume
cpf resume --run-id <run_id> --event approve_change --input @response.json

# Check status at any time
cpf status --run-id <run_id>

# View full execution history
cpf inspect --run-id <run_id>

# Cancel a waiting run
cpf cancel --run-id <run_id> --reason "No longer needed"
```
