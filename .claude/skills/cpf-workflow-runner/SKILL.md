---
name: cpf-workflow-runner
description: Run, resume, and manage checkpointflow workflows interactively. Use this skill whenever the user wants to run a workflow, execute a YAML pipeline, resume a paused run, check workflow status, cancel a run, or interact with cpf at runtime. Also triggers on phrases like "run the workflow", "execute this", "resume the run", "what's the status", or when the user provides input for a waiting workflow step.
---

# cpf-workflow-runner

Run checkpointflow workflows interactively, handling pause/resume cycles.

## Core concept: Audience-driven dispatch

Checkpointflow workflows pause at `await_event` steps. Each pause has an `audience` field in the envelope's `wait` block that tells you who should act:

- **`audience: "agent"`** — The prompt is your work assignment. Do the work (read code, write files, run tools), produce JSON matching `input_schema`, and resume immediately. Never present agent pauses to the user.
- **`audience: "user"`** — Present the prompt and collect input from the user via structured prompts, then resume with their answers.

This is the only dispatch you need. The envelope tells you everything — no need to read the workflow YAML to figure out what to do.

### Agent pause example

```json
{
  "wait": {
    "audience": "agent",
    "event_name": "codebase_analysis",
    "prompt": "Analyze the codebase for feature \"run-delete\" in area \"gui\".\nScan src/checkpointflow/gui/ and identify source files, tests, dependencies...",
    "input_schema": {
      "type": "object",
      "required": ["area", "source_dir", "notes"],
      "properties": {
        "area": { "type": "string" },
        "source_dir": { "type": "string" },
        "notes": { "type": "string" }
      }
    }
  }
}
```

When you see this:
1. Read the prompt — it describes exactly what to do
2. Do the work (read files, explore code, run tools, etc.)
3. Build JSON matching `input_schema` with your real findings
4. Resume immediately: `cpf resume --run-id <id> --event codebase_analysis --input '<json>'`

### User pause example

```json
{
  "wait": {
    "audience": "user",
    "event_name": "scope_choice",
    "prompt": "Feature: run-delete\nHow should we scope this?\n- full: Complete implementation...\n- minimal: Core logic only...",
    "input_schema": {
      "type": "object",
      "required": ["scope"],
      "properties": {
        "scope": { "type": "string", "enum": ["full", "minimal", "spike", "cancel"] }
      }
    }
  }
}
```

When you see this:
1. Present the prompt context to the user
2. Collect their input via structured prompts (AskUserQuestion)
3. Resume: `cpf resume --run-id <id> --event scope_choice --input '{"scope": "full"}'`

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
| 40 | Waiting for input | Enter the interactive loop (dispatches on audience). |
| 10 | Validation error | Show `error.message`. Check inputs match the schema. |
| 30 | Step failed | Show which step failed and why. Offer to inspect with `cpf inspect`. |
| 80 | Unsupported step | Tell the user this step kind isn't implemented yet. |
| Other | Error | Show the error and suggest next steps. |

## Interactive loop (await_event handling)

This is the core of the skill. When a workflow pauses (exit code 40), the envelope contains a `wait` block. Dispatch on `wait.audience`:

### Agent audience (`wait.audience == "agent"`)

The prompt is your work assignment. Do not present it to the user.

1. **Read `wait.prompt`** — it describes the work to do, with full context from previous steps already interpolated in.
2. **Do the work** — read code, write files, run tools, explore the codebase — whatever the prompt asks for.
3. **Build event JSON** matching `wait.input_schema` with your real results.
4. **Resume immediately:**
   ```bash
   cpf resume --run-id <run_id> --event <event_name> --input '<event_json>'
   ```
5. **Parse the new envelope** and loop back.

### User audience (`wait.audience == "user"`)

Present the checkpoint to the user and collect their input.

1. **Read the wait block** — extract `prompt`, `input_schema`, `event_name`, and `run_id`.

2. **Collect input using AskUserQuestion** — map each field in `input_schema` to a question using the same option-building rules from Step 3 above:
   - `enum` → one option per value
   - `boolean` → "Yes" / "No"
   - `examples` array → one option per example (user can always pick "Other")
   - Free-text without examples → craft 2 realistic example values from context

   **Multiple fields:** If `input_schema` has multiple `required` fields, ask them together in a single prompt call when possible. Optional fields can be asked in a follow-up or skipped.

   **Use the `prompt` from the wait block** as context when presenting the questions — it explains what the user is deciding on.

3. **Build the event JSON** from the user's answers. Map each answer back to the field name in `input_schema`. Make sure the result matches the schema types (strings stay strings, numbers get parsed).

4. **Resume the workflow:**
   ```bash
   cpf resume --run-id <run_id> --event <event_name> --input '<event_json>'
   ```

5. **Parse the new envelope** and loop back:
   - If exit code 0 → done, show result
   - If exit code 40 → another await_event, dispatch on audience again
   - If error → show it

Keep looping until the workflow completes, fails, or the user wants to stop.

**Example interaction flow:**

```
User: run the feature development workflow
→ cpf run -f examples/cpf_feature_development.yaml --input '{"feature_name": "run-delete", ...}'
→ Exit 40: audience=agent at "analyze_codebase"
  → Read prompt, analyze the codebase for real
  → Resume with real findings JSON
→ Exit 40: audience=user at "scope_decision"
  → Present analysis results + structured prompt for scope
  → User picks "full"
  → Resume with {"scope": "full"}
→ Exit 40: audience=agent at "tdd_plan"
  → Read prompt, design real test plan
  → Resume with test plan JSON
→ Exit 40: audience=user at "review_tdd_plan"
  → Present TDD plan + structured prompt for approval
  → User picks "approve"
  → Resume with {"decision": "approve"}
→ Exit 40: audience=agent at "write_tests"
  → Write real test files
  → Resume with results
→ Exit 40: audience=agent at "implement_feature"
  → Write production code, run tests
  → Resume with results
→ Exit 40: audience=agent at "quality_gate"
  → Run ruff, mypy, pytest — fix issues
  → Resume with pass/fail results
→ (gate_result switch routes to final_review)
→ Exit 40: audience=user at "final_review"
  → Present quality results + structured prompt
  → User picks "ship_it"
  → Resume
→ Exit 0: completed
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

- **Agent pauses are auto-resume** — never present them to the user. Do the work silently and resume.
- **The prompt has full context** via interpolation — you do not need to read the workflow YAML to understand the work. The prompt already references previous step outputs.
- **If you can't complete agent work**, still provide valid JSON with honest status fields (e.g., `lint_ok: false`, `implemented: false`). The workflow's branching logic handles failure paths.
- Always parse the JSON envelope — don't rely on exit codes alone. The envelope has richer information.
- Exit code 40 is not an error. Don't treat it as a failure or apologize for it.
- When showing results to the user, format them nicely — don't dump raw JSON unless they ask for it.
- If a workflow has multiple sequential `await_event` steps (like a quiz), keep the loop going smoothly without re-explaining the process each time.
- The `--input` flag accepts either inline JSON (`'{"key": "value"}'`) or a file reference (`@path/to/file.json`). Prefer inline for simple inputs.
- Use `workflow_name` and `workflow_description` from the envelope to provide context to the user, especially on the first interaction.
