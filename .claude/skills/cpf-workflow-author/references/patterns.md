# Common Workflow Patterns

Read this file when you need inspiration for structuring a workflow. Each pattern shows a minimal example you can adapt.

## Table of Contents

1. [Linear pipeline](#linear-pipeline)
2. [Approval gate](#approval-gate)
3. [Agent work step](#agent-work-step)
4. [Multi-branch decision](#multi-branch-decision)
5. [Conditional skip](#conditional-skip)
6. [Data pipeline with output chaining](#data-pipeline-with-output-chaining)
7. [Quiz / multi-step interaction](#quiz--multi-step-interaction)

---

## Linear pipeline

Run a sequence of commands with no human interaction.

```yaml
schema_version: checkpointflow/v1
workflow:
  id: deploy_pipeline
  name: Deploy Pipeline
  version: 0.1.0
  description: >
    Builds, tests, and deploys to the target environment in sequence.
    No human approval gates — use for trusted environments like dev/staging.
  inputs:
    type: object
    required: [environment]
    properties:
      environment:
        type: string
        description: Target deployment environment — determines config and secrets
        examples: ["staging", "production", "dev"]

  steps:
    - id: build
      kind: cli
      command: make build ENV=${inputs.environment}

    - id: test
      kind: cli
      command: make test

    - id: deploy
      kind: cli
      command: make deploy ENV=${inputs.environment}

    - id: done
      kind: end
      result:
        deployed_to: ${inputs.environment}
```

## Approval gate

Run a command, pause for human approval, then continue or abort.

```yaml
steps:
  - id: plan
    kind: cli
    command: terraform plan -out=plan.tfplan
    timeout_seconds: 300

  - id: approval
    kind: await_event
    audience: user
    event_name: deploy_approval
    prompt: Review the Terraform plan and approve or reject the deployment.
    input_schema:
      type: object
      required: [decision]
      properties:
        decision: { type: string, enum: [approve, reject] }
    transitions:
      - when: ${event.decision == "approve"}
        next: apply
      - when: ${event.decision == "reject"}
        next: aborted

  - id: apply
    kind: cli
    command: terraform apply plan.tfplan

  - id: complete
    kind: end
    result: { status: applied }

  - id: aborted
    kind: end
    result: { status: rejected }
```

## Agent work step

Pause for an AI agent to perform work and return structured results. The agent reads the prompt as a work assignment, does the actual work, and resumes with output matching the schema. Pair with a user step for human review of agent output.

```yaml
steps:
  - id: analyze
    kind: await_event
    audience: agent
    event_name: analysis_results
    name: "Agent: Analyze Codebase"
    prompt: |
      Analyze the ${inputs.target} directory and identify:
      - Source files and their responsibilities
      - Test coverage gaps
      - Key dependencies
    input_schema:
      type: object
      required: [files_found, test_gaps]
      properties:
        files_found: { type: array, items: { type: string } }
        test_gaps: { type: array, items: { type: string } }
        notes: { type: string }

  - id: review
    kind: await_event
    audience: user
    event_name: review_decision
    prompt: |
      Analysis found ${steps.analyze.outputs.files_found} files.
      Test gaps: ${steps.analyze.outputs.test_gaps}

      Approve or request changes?
    input_schema:
      type: object
      required: [decision]
      properties:
        decision: { type: string, enum: [approve, revise] }
    transitions:
      - when: ${event.decision == "approve"}
        next: implement
      - when: ${event.decision == "revise"}
        next: revision

  - id: implement
    kind: await_event
    audience: agent
    event_name: implementation
    name: "Agent: Implement Changes"
    prompt: |
      Implement fixes for the test gaps identified:
      ${steps.analyze.outputs.test_gaps}
    input_schema:
      type: object
      required: [completed]
      properties:
        completed: { type: boolean }
        files_changed: { type: array, items: { type: string } }

  - id: done
    kind: end
    result: { status: completed }

  - id: revision
    kind: end
    result: { status: needs_revision }
```

The key pattern: `audience: agent` steps have prompts that describe real work, and `input_schema` defines the deliverable. `audience: user` steps present findings and collect decisions.

## Multi-branch decision

Pause for input with more than two choices, routing to different steps.

```yaml
steps:
  - id: triage
    kind: await_event
    audience: agent
    event_name: triage_decision
    prompt: Classify this issue as bug, feature, or question.
    input_schema:
      type: object
      required: [category]
      properties:
        category: { type: string, enum: [bug, feature, question] }
    transitions:
      - when: ${event.category == "bug"}
        next: handle_bug
      - when: ${event.category == "feature"}
        next: handle_feature
      - when: ${event.category == "question"}
        next: handle_question

  - id: handle_bug
    kind: cli
    command: gh issue edit ${inputs.issue_id} --add-label bug

  - id: bug_done
    kind: end
    result: { routed_to: bug }

  - id: handle_feature
    kind: cli
    command: gh issue edit ${inputs.issue_id} --add-label enhancement

  - id: feature_done
    kind: end
    result: { routed_to: feature }

  - id: handle_question
    kind: cli
    command: gh issue edit ${inputs.issue_id} --add-label question

  - id: question_done
    kind: end
    result: { routed_to: question }
```

Note how each branch has its own `end` step so execution doesn't fall through into the next branch.

## Conditional skip

Use `if` to skip steps based on input without branching.

```yaml
steps:
  - id: lint
    kind: cli
    command: npm run lint

  - id: typecheck
    kind: cli
    command: npm run typecheck
    if: inputs.strict == "true"

  - id: test
    kind: cli
    command: npm test

  - id: done
    kind: end
    result: { checks: passed }
```

## Data pipeline with output chaining

Pass structured JSON between steps using `outputs`.

```yaml
steps:
  - id: fetch
    kind: cli
    command: curl -s https://api.example.com/data/${inputs.id}
    outputs:
      type: object
      required: [name, score]
      properties:
        name: { type: string }
        score: { type: number }

  - id: report
    kind: cli
    command: echo "Score for ${steps.fetch.outputs.name} is ${steps.fetch.outputs.score}"

  - id: done
    kind: end
    result:
      name: ${steps.fetch.outputs.name}
      score: ${steps.fetch.outputs.score}
```

## Quiz / multi-step interaction

Chain multiple `await_event` steps to collect input across several rounds. Use transitions to skip feedback for correct answers.

```yaml
steps:
  - id: q1
    kind: await_event
    audience: user
    event_name: q1_answer
    prompt: "What is 2 + 2? a) 3 b) 4 c) 5"
    input_schema:
      type: object
      required: [answer]
      properties:
        answer: { type: string, enum: [a, b, c] }
    transitions:
      - when: ${event.answer == "b"}
        next: q2
      - when: ${event.answer != "b"}
        next: q1_wrong

  - id: q1_wrong
    kind: cli
    command: echo "The answer was b) 4"

  - id: q2
    kind: await_event
    audience: user
    event_name: q2_answer
    prompt: "What is 3 * 3? a) 6 b) 8 c) 9"
    input_schema:
      type: object
      required: [answer]
      properties:
        answer: { type: string, enum: [a, b, c] }
    transitions:
      - when: ${event.answer == "c"}
        next: passed
      - when: ${event.answer != "c"}
        next: q2_wrong

  - id: q2_wrong
    kind: cli
    command: echo "The answer was c) 9"

  - id: passed
    kind: end
    result: { status: quiz_complete }
```
