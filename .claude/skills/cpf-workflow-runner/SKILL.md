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
2. Collect their input via structured prompts
3. Resume: `cpf resume --run-id <id> --event scope_choice --input '{"scope": "full"}'`

## Critical: Collect input through structured prompts, not chat

Every time the workflow needs input from the user — whether collecting workflow inputs before `cpf run`, gathering event data at an `await_event` pause, or confirming a cancellation — present structured choices using whatever interactive prompt tool is available in your environment (e.g., a question/answer UI, a selection picker, a form). The user should experience the workflow as a guided flow where they pick options and provide values through structured prompts, not by typing free-form messages into chat.

Do not say "what would you like to do?" and wait for a text reply. Always present choices and collect input through a structured prompt tool.

## Running a workflow

### Step 1: Discover and understand the flow

Use `cpf flows` to list available workflows, then `cpf flows --detail <id>` to see everything about a specific flow — description, required/optional inputs with types and descriptions, step overview, and a ready-to-use run command:

```bash
cpf flows                        # List all available workflows
cpf flows --detail <id>          # Full detail: inputs, steps, run command
```

The detail output tells you exactly what inputs to collect and gives you the `cpf run` command template. No need to read the workflow YAML.

### Step 2: Collect inputs and execute

Use the inputs section from `cpf flows --detail` to collect values from the user via structured prompts. **Read the `description` field on each input** — it explains what the value should be and often includes examples or hints (e.g., "Directory containing the tools/ subdirectory").

For inputs you can infer from context, do so without asking:
- `repo_dir` → current working directory
- `artifact_dir` → create a temp directory
- `author` → `git config user.name`
- Paths referencing the current project → resolve from the working directory

Only prompt the user for inputs that are genuinely ambiguous. For each prompted input, build options using this priority:

1. **`enum` values** → one option per enum value (the user picks one)
2. **`type: boolean`** → two options: "Yes" / "No"
3. **`examples` array** → one option per example value (user picks one or types custom)
4. **No examples** → craft 2 realistic example values from the description

**Never create placeholder options** like "Type value" or "Enter value". Every option should be a real, plausible value the user might choose.

Then run:

```bash
cpf run -f <path> --input '<json>'
```

Parse the JSON envelope from stdout. The `ok`, `status`, and `exit_code` fields tell you what happened.

### Step 3: Handle the result

Based on `exit_code`:

| Exit code | What happened | What to do |
|-----------|--------------|------------|
| 0 | Completed | Show the `result` to the user. Done. |
| 40 | Waiting for input | Enter the interactive loop (dispatches on audience). |
| 10 | Validation error | Show `error.message`. Check inputs match the schema. |
| 30 | Step failed | Immediately run `cpf inspect --run-id <id>`, read the `stderr_path` from the failed step result, and diagnose the root cause before reporting to the user. |
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

2. **Collect input** — map each field in `input_schema` to a structured prompt using the same option-building rules from Step 2 above.

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

## Never modify workflow files during an active run

cpf checksums the workflow YAML when a run starts and verifies it on every resume. If you edit the workflow file while a run is in progress, the next `cpf resume` will fail with `ERR_VALIDATION_WORKFLOW` ("Workflow file has changed since the run started"). This forces you to abandon the run and start over.

If you need to fix the workflow YAML mid-session, finish or cancel the active run first.

## Parallel agents with sequential callbacks

Some workflows have multiple sequential `await_event` steps that are all `audience: "agent"` — for example, 4 specialist reviews that each get their own callback. The optimal pattern:

1. **Launch all agents in parallel** (background agents) when you first see the sequence.
2. **Write event JSON files** as each agent completes — don't hold results in memory.
3. **Resume callbacks sequentially** as the workflow reaches each one, using the pre-written files.

Agents may finish out of order. That's fine — queue their results in files and feed them to the workflow in the order it expects.

## Windows path handling

On Windows, backslashes in file paths break inline JSON (`--input '{"file": "C:\\..."}'` causes JSON parse errors). Two options:

- **Use `@file` references** (preferred): write event JSON to a file, then `--input @path/to/event.json`
- **Use forward slashes** in inline JSON: `"C:/Users/thoma/..."` — cpf and Python accept these on Windows

When using `@file`, make sure you know the actual Windows path — different tools may resolve `/tmp/` to different locations (e.g., `C:\tmp\` vs `C:\Users\...\AppData\Local\Temp\`).

## Tips

- **Agent pauses are auto-resume** — never present them to the user. Do the work silently and resume.
- **The prompt has full context** via interpolation — you do not need to read the workflow YAML to understand the work. The prompt already references previous step outputs.
- **If you can't complete agent work**, still provide valid JSON with honest status fields (e.g., `lint_ok: false`, `implemented: false`). The workflow's branching logic handles failure paths.
- Always parse the JSON envelope — don't rely on exit codes alone. The envelope has richer information.
- Exit code 40 is not an error. Don't treat it as a failure or apologize for it.
- When showing results to the user, format them nicely — don't dump raw JSON unless they ask for it.
- If a workflow has multiple sequential `await_event` steps (like a quiz), keep the loop going smoothly without re-explaining the process each time.
- The `--input` flag accepts either inline JSON (`'{"key": "value"}'`) or a file reference (`@path/to/file.json`). Prefer `@file` for any input containing file paths or long strings.
