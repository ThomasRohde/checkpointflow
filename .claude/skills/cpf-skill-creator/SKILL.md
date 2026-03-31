---
name: cpf-skill-creator
description: Create and improve Claude Code skills using a structured checkpointflow workflow with test-driven iteration. Use this skill whenever the user wants to create a skill, make a skill, build a skill, improve an existing skill, test a skill with evals, benchmark skill quality, optimize a skill description, or turn a conversation into a reusable skill. Also triggers on "skill for X", "automate this as a skill", "package this as a skill", and similar phrases. Always use this instead of the generic skill-creator when in the checkpointflow repo.
---

# cpf-skill-creator

Create and improve Claude Code skills through a structured, workflow-driven process powered by checkpointflow.

## How it works

This skill wraps the skill creation process in a cpf workflow (`workflows/skill-creator.yaml`) that orchestrates the full lifecycle: capture intent, draft, test, grade, iterate, optimize, and package. The workflow uses audience-driven dispatch — agent steps do the work automatically, user steps pause for human decisions.

Run the workflow via the `cpf-workflow-runner` skill or directly:

```bash
cpf run -f .claude/skills/cpf-skill-creator/skill-creator.yaml --input '{"skill_name": "my-skill", "intent": "..."}'
```

The workflow handles:
1. **Capture intent** (user) — Refine what the skill does and when it triggers
2. **Research & draft** (agent) — Create the SKILL.md and test cases
3. **Review draft** (user) — Approve, revise, or cancel
4. **Run tests & grade** (agent) — Execute evals, grade, benchmark, launch viewer
5. **Review results** (user) — Examine outputs, decide to iterate/optimize/ship
6. **Improve skill** (agent) — Apply feedback, rewrite (loops back to step 4)
7. **Optimize description** (agent) — Tune triggering accuracy
8. **Package** (agent) — Create .skill file for distribution

## Reference material: Anthropic skill-creator

This skill delegates to utilities from the official Anthropic skill-creator plugin rather than duplicating them. The reference path is:

```
~/.claude/plugins/cache/claude-plugins-official/skill-creator/unknown/skills/skill-creator/
```

Available utilities at that path:

| Path | Purpose |
|------|---------|
| `scripts/aggregate_benchmark.py` | Aggregate grading into benchmark.json |
| `scripts/package_skill.py` | Package skill as .skill file |
| `scripts/run_loop.py` | Description optimization loop |
| `scripts/run_eval.py` | Run trigger evaluation |
| `eval-viewer/generate_review.py` | Generate HTML review viewer |
| `agents/grader.md` | Grading instructions for subagents |
| `agents/analyzer.md` | Benchmark analysis instructions |
| `agents/comparator.md` | Blind A/B comparison instructions |
| `assets/eval_review.html` | Template for trigger eval review UI |
| `references/schemas.md` | JSON schemas for evals, grading, benchmark |

When running Python scripts from the reference path, set the working directory to the skill-creator root so module imports resolve correctly:

```bash
cd ~/.claude/plugins/cache/claude-plugins-official/skill-creator/unknown/skills/skill-creator
python -m scripts.aggregate_benchmark <workspace>/iteration-1 --skill-name my-skill
```

If the reference path doesn't exist (plugin not installed), fall back to manual operations — grade inline, skip the viewer, and package by hand.

## Skill writing principles

These principles apply when drafting or improving skills in the agent steps:

**Description field is king.** It's the primary triggering mechanism. Include both what the skill does AND specific contexts/phrases. Claude tends to under-trigger, so make descriptions slightly "pushy" — enumerate trigger phrases generously.

**Progressive disclosure.** Keep SKILL.md under 500 lines. Put detailed reference material in `references/` subdirectories. Put scripts in `scripts/`. The model reads SKILL.md on trigger and only loads bundled resources when needed.

**Explain the why.** Today's LLMs respond better to reasoning than to rigid ALWAYS/NEVER rules. Explain why each instruction matters so the model can generalize to edge cases.

**Examples over abstractions.** Include concrete input/output examples. They're worth more than paragraphs of description.

**Look for repeated patterns.** If test runs independently produce similar helper scripts, bundle that script into the skill. Write it once in `scripts/` and reference it.

## Iteration philosophy

When improving a skill after user feedback:

- **Generalize** from the specific feedback. The skill will be used across many prompts, not just the test cases. Don't overfit.
- **Keep it lean.** Remove instructions that aren't pulling their weight. Read the test transcripts — if the skill is making the model waste time, cut those parts.
- **Explain the why.** If you find yourself writing ALL-CAPS MUST/NEVER, reframe as reasoning the model can internalize.
- **Draft, then revise.** Write the improvement, then read it fresh and tighten it.

## Workspace layout

Test results and artifacts are organized in `<skill-name>-workspace/` alongside the skill:

```
<skill-name>-workspace/
  evals/
    evals.json                    # Test prompts and assertions
  iteration-1/
    eval-0-<descriptive-name>/
      with_skill/
        outputs/                  # Files produced with the skill
        grading.json              # Assertion pass/fail results
        timing.json               # Tokens and duration
      without_skill/
        outputs/                  # Baseline outputs
        grading.json
        timing.json
      eval_metadata.json          # Prompt, assertions for this eval
    benchmark.json                # Aggregated metrics
    benchmark.md                  # Human-readable summary
    feedback.json                 # User feedback from the viewer
  iteration-2/
    ...
```

## Quick start for improving an existing skill

If the user has an existing skill they want to improve, pass it via the `existing_skill_path` input:

```bash
cpf run -f workflows/skill-creator.yaml --input '{
  "skill_name": "my-skill",
  "intent": "Improve test coverage and fix edge case handling",
  "existing_skill_path": ".claude/skills/my-skill"
}'
```

The workflow will snapshot the existing skill for baseline comparison, then iterate.

## Tips

- The workflow handles orchestration; each agent step does the actual work (reading code, writing files, running tools).
- Always use `generate_review.py` from the reference path — never write custom HTML for the viewer.
- For headless environments, pass `--static <output.html>` to `generate_review.py`.
- The `--previous-workspace` flag on `generate_review.py` enables iteration-over-iteration comparison.
- If subagents aren't available, run test cases inline (less rigorous but still useful with human review).
- Description optimization requires the `claude` CLI (`claude -p`). Skip it if not available.
