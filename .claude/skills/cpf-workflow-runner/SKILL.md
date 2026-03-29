---
name: cpf-workflow-runner
description: Run, resume, and manage checkpointflow workflows interactively. Use this skill whenever the user wants to run a workflow, execute a YAML pipeline, resume a paused run, check workflow status, cancel a run, or interact with cpf at runtime. Also triggers on phrases like "run the workflow", "execute this", "resume the run", "what's the status", or when the user provides input for a waiting workflow step.
---

# cpf-workflow-runner

Run checkpointflow workflows interactively, handling pause/resume cycles with the user.

## Core concept: You are the agent

Checkpointflow orchestrates collaboration between humans and AI agents. The engine handles sequencing, checkpoints, and state — but **you are the agent**. When the workflow contains `cli` steps that describe agent work, the `echo` command is a structural placeholder that feeds the engine the output it needs to advance. The actual work is your responsibility.

### Recognizing agent steps

A step is agent-directed when:

- Its name is prefixed with "Agent:" (e.g., `"Agent: Write Failing Tests"`)
- Its description contains action verbs implying real work (e.g., "Scan the relevant source area and identify files, tests, and dependencies")
- Its command is an `echo` outputting static or templated JSON — not a real tool invocation

Steps prefixed "Human:" or "System:" are not agent-directed. Human steps are `await_event` checkpoints. System steps are `switch`/`parallel`/`end` — handled by the engine.

### When to do the work

The engine runs all steps between pause points automatically. By the time you see the envelope, the agent `cli` steps have already "completed" with their echo output. The `await_event` checkpoints are your natural intervention points.

**At each pause, before presenting the checkpoint to the user:**

1. Read the workflow YAML (if you haven't already) to identify which agent steps just executed since the last pause
2. Do the actual work each step describes — use the step's `name`, `description`, and `outputs` schema as your assignment
3. Present your real results to the user alongside the checkpoint prompt

The `wait.prompt` will contain interpolated values from the echo outputs (e.g., fake file lists, hardcoded test counts). Replace these with your real findings when presenting to the user.

### Example: what "doing the work" looks like

Given this step in the workflow:
```yaml
- id: analyze_codebase
  kind: cli
  name: "Agent: Analyze Affected Area"
  description: Scan the relevant source area and identify files, tests, and dependencies
  command: echo '{"area":"gui", "source_dir":"src/checkpointflow/gui/", ...}'
```

Don't just let the echo run and move on. Actually:
- Read files in the source directory
- Find existing test files
- Identify imports and dependencies
- Assess schema impact

Then present your real findings at the checkpoint that follows.

For a step like `"Agent: Write Failing Tests"` — actually write test files. For `"Agent: Implement Feature"` — actually write production code. For quality gate steps — actually run `uv run pytest`, `uv run ruff check .`, `uv run mypy`.

### Multiple agent steps between pauses

Sometimes several agent steps run before the next checkpoint (e.g., write tests → implement → lint → typecheck → test → gate check → review). Do all of that work at the pause. The workflow structure tells you the order and what each step expects.

## Critical: Collect input through structured prompts, not chat

Every time the workflow needs input from the user — whether collecting workflow inputs before `cpf run`, gathering event data at an `await_event` pause, or confirming a cancellation — present structured choices using whatever interactive prompt tool is available in your environment (e.g., a question/answer UI, a selection picker, a form). The user should experience the workflow as a guided flow where they pick options and provide values through structured prompts, not by typing free-form messages into chat.

Do not say "what would you like to do?" and wait for a text reply. Always present choices and collect input through a structured prompt tool.

## Finding workflows

When the user asks to run a workflow without giving a full path, search these locations in order:

1. The path the user provided (if any)
2. `.checkpointflow/` in the current working directory
3. `~/.checkpointflow/`
4. `examples/` in the current project (if it's a checkpointflow repo)

Use glob patterns like `**/*.yaml` to find workflow files. If multiple matches exist, use a structured prompt tool to let the user pick which one.

If no workflows are found, tell the user and suggest they create one (the `cpf-workflow-author` skill can help with that).

## Running a workflow

### Step 1: Present the workflow

When the envelope comes back (from `cpf run` or `cpf resume`), use `workflow_name` and `workflow_description` from the JSON envelope to introduce the workflow to the user. This gives context even if you haven't read the YAML file.

### Step 2: Identify inputs

Read the workflow YAML to check what inputs it requires:
- Look at `workflow.inputs.required` and `workflow.inputs.properties`
- If the user hasn't provided inputs, use a structured prompt tool to collect them
- For complex inputs, ask the user to provide JSON

### Step 3: Build good prompt options from the schema

For each input property, build AskUserQuestion options using this priority:

1. **`enum` array** → one option per enum value (the user picks one)
2. **`type: boolean`** → two options: "Yes" / "No"
3. **`examples` array** → one option per example value (the user picks one or types "Other" for a custom value). This is the key mechanism for free-text fields — workflow authors provide examples that become real, meaningful options.
4. **`description` with inline examples** → if the description contains patterns like `e.g. "foo", "bar"` or `(e.g. "foo", "bar")`, extract those values and use them as options
5. **No examples available** → use the `description` text itself to craft 2 meaningful, distinct example options that illustrate the expected format

**Never create placeholder options** like "Type value" or "Enter value". Every option should be a real, plausible value the user might choose.

### Step 4: Execute

```bash
cpf run -f <path> --input '<json>'
```

Parse the JSON envelope from stdout. The `ok`, `status`, and `exit_code` fields tell you what happened.

### Step 5: Handle the result

Based on `exit_code`:

| Exit code | What happened | What to do |
|-----------|--------------|------------|
| 0 | Completed | Show the `result` to the user. Done. |
| 40 | Waiting for input | **Do agent work first** (see below), then enter the interactive loop. |
| 10 | Validation error | Show `error.message`. Check inputs match the schema. |
| 30 | Step failed | Show which step failed and why. Offer to inspect with `cpf inspect`. |
| 80 | Unsupported step | Tell the user this step kind isn't implemented yet. |
| Other | Error | Show the error and suggest next steps. |

### Step 5a: Do agent work before presenting checkpoints

When exit code is 40, before asking the user for input:

1. Look at the workflow YAML — identify every agent-directed `cli` step that ran between the start (or last pause) and the current `await_event`
2. Execute the real work each step describes (read code, write files, run commands, etc.)
3. Present your actual findings/results to the user as context for their decision

This is the step that makes the workflow real — without it, you're just passing fake echo output through human checkpoints.

## Interactive loop (await_event handling)

This is the core of the skill. When a workflow pauses at an `await_event` step (exit code 40), do any pending agent work first (see "Core concept" above), then handle the checkpoint. The envelope contains a `wait` block:

```json
{
  "workflow_name": "My Workflow",
  "workflow_description": "What this workflow does",
  "wait": {
    "audience": "user",
    "event_name": "approval",
    "prompt": "Review and approve or reject.",
    "input_schema": { ... },
    "resume": {
      "command": "cpf resume --run-id <id> --event approval --input @event.json"
    }
  }
}
```

Handle it like this:

1. **Read the wait block** — extract `prompt`, `input_schema`, `event_name`, and `run_id`.

2. **Collect input using AskUserQuestion** — map each field in `input_schema` to a question using the same option-building rules from Step 3 above:
   - `enum` → one option per value
   - `boolean` → "Yes" / "No"
   - `examples` array → one option per example (user can always pick "Other")
   - Free-text without examples → craft 2 realistic example values from context

   **Multiple fields:** If `input_schema` has multiple `required` fields, ask them together in a single prompt call when possible. Optional fields can be asked in a follow-up or skipped.

   **Use the `prompt` from the wait block** as context when presenting the questions — it explains what the user is deciding on.

   **Example:** For this schema:
   ```json
   {"required": ["decision"], "properties": {"decision": {"type": "string", "enum": ["approve", "reject"]}, "notes": {"type": "string"}}}
   ```
   Present a structured prompt with:
   - Question 1 (Decision): options "approve" / "reject"
   - Question 2 (Notes): options "No notes" / "Looks good, minor nits" (realistic examples, not placeholders)

3. **Build the event JSON** from the user's answers. Map each answer back to the field name in `input_schema`. Make sure the result matches the schema types (strings stay strings, numbers get parsed).

4. **Resume the workflow:**
   ```bash
   cpf resume --run-id <run_id> --event <event_name> --input '<event_json>'
   ```

5. **Parse the new envelope** and loop back:
   - If exit code 0 → done, show result
   - If exit code 40 → another await_event, repeat from step 1
   - If error → show it

Keep looping until the workflow completes, fails, or the user wants to stop.

**Example interaction flow (with agent work):**

```
User: run the feature development workflow
→ cpf run -f examples/cpf_feature_development.yaml --input '{"feature_name": "run-delete", ...}'
→ Exit 40: waiting at "scope_decision" step
→ Agent step "analyze_codebase" just ran — DO THE ACTUAL WORK:
  - Read src/checkpointflow/gui/ to find relevant files
  - Find existing tests in tests/test_gui*.py
  - Identify dependencies and schema impact
→ Present real findings + structured prompt for scope choice
→ User picks "full"
→ cpf resume --run-id abc123 --event scope_choice --input '{"scope": "full"}'
→ Exit 40: waiting at "review_tdd_plan" step
→ Agent step "tdd_plan" just ran — DO THE ACTUAL WORK:
  - Design real test cases based on the codebase analysis
  - Plan the implementation approach
→ Present real TDD plan + structured prompt for approval
→ User picks "approve"
→ cpf resume --run-id abc123 --event tdd_review --input '{"decision": "approve"}'
→ Exit 40: waiting at "final_review" step
→ Agent steps "write_tests", "implement_feature", quality gate all ran — DO THE ACTUAL WORK:
  - Write real test files
  - Implement the feature code
  - Run uv run ruff check ., uv run mypy, uv run pytest
→ Present real results + structured prompt for ship/revise
→ User picks "ship_it"
→ cpf resume → Exit 0: completed
```

## Status and inspection

When the user asks about a run:

```bash
cpf status --run-id <run_id>    # Quick status check
cpf inspect --run-id <run_id>   # Full execution history
```

If the user doesn't remember the run ID, check recent output from previous commands in the conversation — the `run_id` is in every envelope.

## Cancelling a run

When the user wants to cancel a waiting run:

```bash
cpf cancel --run-id <run_id> --reason "<reason>"
```

Use a structured prompt to confirm before cancelling, and ask for a reason if not provided.

## Web dashboard

Launch the GUI to browse workflows and runs visually:

```bash
cpf gui                    # opens http://localhost:8420
cpf gui --port 9000        # custom port
```

The dashboard shows workflow graphs with all step types rendered, run history with search/sort, and step detail panels.

## Tips

- **Agent steps are work assignments, not status updates.** When a step says "Agent: Write Failing Tests", write tests. Don't just watch the echo command produce fake output.
- **Read the workflow YAML early.** You need it to know which agent steps ran between pauses so you can do the work before presenting each checkpoint.
- Always parse the JSON envelope — don't rely on exit codes alone. The envelope has richer information.
- Exit code 40 is not an error. Don't treat it as a failure or apologize for it.
- When showing results to the user, format them nicely — don't dump raw JSON unless they ask for it.
- If a workflow has multiple sequential `await_event` steps (like a quiz), keep the loop going smoothly without re-explaining the process each time.
- The `--input` flag accepts either inline JSON (`'{"key": "value"}'`) or a file reference (`@path/to/file.json`). Prefer inline for simple inputs.
- Use `workflow_name` and `workflow_description` from the envelope to provide context to the user, especially on the first interaction.
- For quality gate steps that specify commands like lint/typecheck/test, run the real tools (`uv run ruff check .`, `uv run mypy`, `uv run pytest`) — don't rely on the hardcoded echo output.
