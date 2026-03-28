# Contributing

## Development model

This project uses test-driven development.

For every behavior change:

1. write or update a failing test
2. run the smallest possible test target and confirm it fails for the intended reason
3. implement the minimum change to make the test pass
4. refactor while keeping the test green
5. run the full quality gate before considering the change complete

## Test layering

- Unit tests should cover pure logic first: workflow parsing, schema validation, expression evaluation, state transitions, and persistence helpers.
- Integration tests should cover command-level behavior such as `cpf validate`, `cpf run`, and `cpf resume`.
- Regression tests should be added for every reported bug before the fix is implemented.

## Local workflow

```bash
uv sync --group dev
uv run python scripts/install_git_hooks.py
uv run pytest tests/test_cli_smoke.py -q
uv run pytest -x
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

## Git hooks

This repository includes repo-local hooks under `.githooks/`.

Install them once per clone:

```bash
uv run python scripts/install_git_hooks.py
```

The hooks enforce:

- `pre-commit`: `uv lock --check`, `ruff format --check`, `ruff check`, `mypy`
- `pre-push`: full `pytest`, `uv build`, and a built-wheel CLI smoke test

To bypass them temporarily for exceptional cases:

```bash
CHECKPOINTFLOW_SKIP_HOOKS=1 git commit -m "..."
```

## Quality gate

A change is not done until all of the following pass:

- relevant targeted tests
- full `pytest` suite
- `ruff check`
- `mypy`
