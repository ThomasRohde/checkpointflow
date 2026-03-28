---
name: cpf-workflow-author
description: Create and edit checkpointflow workflow YAML files. Use this skill whenever the user wants to create a workflow, automate a process as a YAML pipeline, define steps that mix CLI commands with human or agent checkpoints, turn a conversation into a reusable runbook, or asks about writing cpf/checkpointflow workflows. Also use it when you see keywords like "workflow", "runbook", "approval flow", "pause and resume", or "await event" in the context of automation.
---

# cpf-workflow-author

Create checkpointflow workflow YAML files that are valid, idiomatic, and ready to run with `cpf run`.

## Before you start

Read the checkpointflow guide to get the full reference:
```bash
cpf guide
```

If you need to see existing examples in the project, check `examples/*.yaml` in the checkpointflow repo.

## Authoring process

1. **Understand what the user wants to automate.** Ask clarifying questions if needed: What commands or tools are involved? Where does a human or agent need to weigh in? What are the inputs?

2. **Design the step sequence.** Map each action to a step kind:
   - A shell command or script invocation -> `cli`
   - A point where execution must pause for human/agent input -> `await_event`
   - A terminal outcome -> `end`

3. **Write the YAML file.** Place it in the location the user specifies, or default to `examples/<workflow-id>.yaml` if inside the checkpointflow repo.

4. **Validate immediately** after writing:
   ```bash
   cpf validate -f <path-to-workflow.yaml>
   ```
   If validation fails, fix the YAML and re-validate before telling the user the workflow is ready.

5. **Offer to run it** if the user seems ready. When the workflow hits an `await_event` step (exit code 40), use `AskUserQuestion` to collect the required input, then `cpf resume` to continue.

## Workflow file structure

Every workflow file follows this skeleton:

```yaml
schema_version: checkpointflow/v1
workflow:
  id: snake_case_identifier
  name: Human Readable Name
  version: 0.1.0
  description: One-line description of what this workflow does.

  inputs:
    type: object
    required: [field_name]
    properties:
      field_name:
        type: string

  steps:
    - id: first_step
      kind: cli
      command: echo "doing something with ${inputs.field_name}"

    - id: done
      kind: end
      result:
        status: completed
```

Key rules:
- `schema_version` is always `checkpointflow/v1`
- `workflow.id` must be present, snake_case, and unique
- `workflow.inputs` uses JSON Schema to define what the caller must provide
- Every step needs a unique `id`
- Steps execute sequentially unless a transition jumps elsewhere

## Step kinds (runtime-supported)

### cli

Runs a shell command. Supports `${inputs.x}` and `${steps.<id>.outputs.x}` interpolation in the command string.

```yaml
- id: build
  kind: cli
  cwd: ${inputs.project_dir}
  command: npm run build --project ${inputs.project_name}
  timeout_seconds: 120
```

Use `cwd` to set the working directory (supports interpolation). Use `shell` to pick a specific shell (`bash`, `sh`, `powershell`, `pwsh`), or set `defaults.shell` at the workflow level:

```yaml
workflow:
  defaults:
    shell: bash
```

If the command produces structured JSON on stdout, declare `outputs` so the runtime validates it and makes it available to later steps:

```yaml
- id: analyze
  kind: cli
  command: analyze-tool --format json ${inputs.target}
  outputs:
    type: object
    required: [score, report_path]
    properties:
      score: { type: number }
      report_path: { type: string }
```

Use `if` for conditional execution (no `${}` wrapper needed):

```yaml
- id: deep_scan
  kind: cli
  command: scan --deep ${inputs.target}
  if: inputs.mode == "full"
```

### await_event

Pauses the workflow and waits for external input. The CLI exits with code 40 and emits a waiting envelope that tells the caller exactly what input is needed and how to resume.

```yaml
- id: review
  kind: await_event
  audience: user          # who should provide input: user, agent, or system
  event_name: review_decision
  prompt: Review the results and decide whether to proceed.
  input_schema:
    type: object
    required: [decision]
    properties:
      decision:
        type: string
        enum: [approve, reject]
      notes:
        type: string
```

Add `transitions` to branch based on the input received:

```yaml
  transitions:
    - when: ${event.decision == "approve"}
      next: deploy
    - when: ${event.decision == "reject"}
      next: cancelled
```

Without transitions, execution continues to the next step in the array.

### end

Terminates the workflow with an explicit result. The result can interpolate values from earlier steps:

```yaml
- id: done
  kind: end
  result:
    status: success
    url: ${steps.deploy.outputs.url}
```

If no `end` step is present, the workflow completes implicitly after the last step with no result. Use `end` when you want to return meaningful data or when you have multiple terminal states (e.g., approved vs. rejected).

## Expressions

Expressions use `${...}` syntax for interpolation in `command` strings and transition `when` clauses:
- `${inputs.name}` — workflow input
- `${steps.build.outputs.artifact}` — output from a previous step
- `${event.decision}` — event data (only in `when` clauses)

In `if` conditions, write the expression bare (no `${}`):
- `if: inputs.mode == "full"`

Operators: `==`, `!=`, `and`, `or`

## Branching patterns

**Skip a step conditionally** — use `if`:
```yaml
- id: optional_step
  kind: cli
  command: do-extra-work
  if: inputs.thorough == "yes"
```

**Branch after human input** — use `transitions` on `await_event` to jump to different steps based on the response. Make sure every transition target step exists in the steps array:
```yaml
- id: approval
  kind: await_event
  audience: user
  event_name: approval
  prompt: Approve or reject?
  input_schema:
    type: object
    required: [choice]
    properties:
      choice: { type: string, enum: [approve, reject] }
  transitions:
    - when: ${event.choice == "approve"}
      next: do_work
    - when: ${event.choice == "reject"}
      next: rejected

- id: do_work
  kind: cli
  command: echo "approved"

- id: complete
  kind: end
  result: { outcome: approved }

- id: rejected
  kind: end
  result: { outcome: rejected }
```

Be aware that steps between a transition target and the next step will execute sequentially. If `do_work` transitions to step `complete`, but `rejected` comes after `complete` in the array, the `rejected` step will NOT be reached from the `do_work` path — execution flows forward from `do_work` through `complete` and stops at the `end`. Place your branch targets so that sequential fall-through does not hit steps from other branches, or use `end` steps to terminate each branch.

## Common mistakes to avoid

- **Missing `schema_version: checkpointflow/v1`** at the top level — every file needs it.
- **Duplicate step IDs** — each step `id` must be unique across the entire workflow.
- **Transition target doesn't exist** — every `next` value must match an actual step `id`.
- **Using `${}` in `if` conditions** — `if` takes a bare expression, not wrapped in `${}`.
- **Forgetting `input_schema` on `await_event`** — it's required, not optional.
- **Step kind typos** — only `cli`, `await_event`, and `end` are supported at runtime. Others (`api`, `switch`, `foreach`, `parallel`, `workflow`) pass validation but fail at runtime with exit code 80.

## After writing the workflow

Always validate:
```bash
cpf validate -f <path>
```

If the user wants to run it:
```bash
cpf run -f <path> --input '{"key": "value"}'
```

When a run pauses at an `await_event` (exit code 40), the JSON envelope contains a `wait` block with the prompt, input schema, and resume command. Use `AskUserQuestion` to gather the input from the user, then resume:
```bash
cpf resume --run-id <id> --event <event_name> --input '{"key": "value"}'
```
