# checkpointflow spec bundle

This bundle contains a concrete starting point for a CLI-first toolchain for authoring, validating, and running checkpointflows.

The intended shape is:

- broad workflow authoring from human-agent conversations
- deterministic execution and replay-safe control flow
- explicit pause/resume through structured events
- durable handoff across agents, shells, and operators
- a narrow runtime core even when the authoring surface is broader

## Included files

- `checkpointflow-prd.md` — main product and technical spec
- `checkpointflow-guide.md` — guide-command style documentation for `cpf`
- `checkpointflow-phase1-implementation-plan.md` — practical build plan
- `schemas/checkpointflow.schema.json` — workflow document schema
- `schemas/checkpointflow-run-envelope.schema.json` — stdout/result envelope schema
- `examples/publish-confluence-change.yaml` — example checkpointflow
- `examples/input.json` — example workflow input
- `examples/waiting-envelope.json` — example pause output
- `examples/resume-event.json` — example resume payload

## Suggested next moves

1. Implement `cpf validate`, `cpf run`, `cpf resume`, `cpf status`, and `cpf guide`.
2. Keep the runtime core in v1 limited to `cli`, `await_event`, and `end`.
3. Treat `await_event` as the only pause primitive.
4. Validate the package on workflows that combine actions, human input, and agent input generated from conversation.
