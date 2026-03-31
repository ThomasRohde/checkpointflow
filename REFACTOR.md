# Refactoring Roadmap

Larger refactors identified by the full codebase review (2026-03-31) that were deferred
for separate implementation.

## 1. Step dispatch registry

**Current state:** `dispatch_step()` in `src/checkpointflow/engine/steps/dispatch.py` uses a
chain of `isinstance` checks to route each step kind to its handler. The same pattern exists
in `src/checkpointflow/gui/api.py` (`parse_workflow`). Adding a new step kind requires editing
both files, adding imports, and adding branches.

**Proposed approach:** Replace the isinstance chain with a registry dict mapping step kind
strings to handler functions. Populate it at import time or via a decorator on each handler
module. This enables adding new step kinds without touching dispatch.py and opens the door
to third-party step plugins.

```python
# Example registry pattern
_STEP_HANDLERS: dict[str, Callable[[Any, RunContext], StepResult]] = {}

def register(kind: str):
    def decorator(fn):
        _STEP_HANDLERS[kind] = fn
        return fn
    return decorator

def dispatch_step(step, ctx, **kwargs):
    handler = _STEP_HANDLERS.get(step.kind)
    if handler is None:
        return StepResult(success=False, error_message=f"Unknown step kind: {step.kind}")
    return handler(step, ctx, **kwargs)
```

**Affected files:**
- `src/checkpointflow/engine/steps/dispatch.py` (main dispatch)
- `src/checkpointflow/engine/steps/*.py` (each handler gets `@register`)
- `src/checkpointflow/gui/api.py` (workflow parsing step-kind switch)
- `tests/test_dispatch.py`

**Complexity:** Medium. The `parallel_step` handler requires an extra `workflow_steps` kwarg
which breaks the uniform handler signature. This should be resolved by adding `workflow_steps`
to `RunContext` or a broader engine context object.

## 2. Sub-workflow and foreach runner deduplication

**Current state:** Three places implement step-sequence execution logic:
1. `runner.py::_execute_steps()` — the main execution loop with persistence, if-conditions,
   switch jumps, await halting, and end-step termination.
2. `workflow_ref_step.py::execute()` — reimplements a mini execution loop for sub-workflows
   without persistence, if-conditions, or event handling.
3. `foreach_step.py::execute()` — has CLI-step-specific interpolation logic that duplicates
   `cli_step.py`, plus its own iteration/dispatch loop.

Changes to step execution semantics must be applied in all three places. The sub-workflow
handler doesn't support if-conditions, and the foreach handler's CLI special-casing means
api_step or other interpolatable steps in foreach loops don't get item context.

**Proposed approach:** Extract a shared `execute_step_sequence()` function that both the main
runner and sub-handlers call. Parameterize it by:
- Whether to persist results (main runner: yes, sub-workflow: no)
- Whether to handle await_event halting (main runner: yes, sub-workflow: no)
- The evaluation context augmentation (foreach: add item/item_index)

For foreach, instead of pre-interpolating CLI commands, inject `_foreach_item` and
`_foreach_index` into the RunContext inputs dict and let dispatch_step handle the step
normally. This removes the CLI special case and makes all step kinds work in foreach.

**Affected files:**
- `src/checkpointflow/engine/runner.py` (extract shared function)
- `src/checkpointflow/engine/steps/workflow_ref_step.py` (use shared function)
- `src/checkpointflow/engine/steps/foreach_step.py` (use shared function, remove CLI special case)
- `tests/test_step_foreach.py`
- `tests/test_step_workflow_ref.py`
- `tests/test_runner.py`

**Complexity:** High. The three implementations have subtle differences in error handling,
output merging, and control flow. Careful test coverage of edge cases is needed before
extracting the shared function.
