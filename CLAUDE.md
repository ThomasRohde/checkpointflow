# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

This is a greenfield project, so there are no legacy constraints. The codebase is small and focused on a single domain (workflow management), so we can be opinionated about architecture and tooling.

## Build & Quality Commands

All commands use `uv` (not pip or poetry):

```bash
uv sync --group dev          # Install dependencies
uv run pytest                # Run tests (stops on first failure)
uv run ruff check .          # Lint
uv run ruff format --check . # Check formatting
uv run ruff format .         # Auto-format
uv run mypy                  # Type check (strict mode)
uv lock --check              # Validate lockfile
uv build                     # Build distribution
```

## Development Methodology

- **TDD is mandatory**: write a failing test before implementing any behavior change.
- Quality gate (all must pass): `ruff check`, `ruff format --check`, `mypy`, `pytest`.
- Git hooks in `.githooks/` run quality checks on commit and full tests on push. Install with `uv run python scripts/install_git_hooks.py`.

## Code Style

- Python 3.11+ (target-version in ruff and mypy).
- Line length: 100 characters.
- mypy strict mode with `pydantic.mypy` plugin — all code must pass strict type checking.
- Ruff lint rules: B, E, F, I, PTH, RET, RUF, SIM, UP.

## Release Procedure

After every successful commit and push, reinstall the global tool:
```bash
uv tool install -e . --force
```

To cut a release:
1. Bump `version` in `pyproject.toml`
2. Run `uv lock` to update the lockfile
3. Commit: `git add pyproject.toml uv.lock && git commit -m "Bump version to X.Y.Z"`
4. Tag: `git tag vX.Y.Z`
5. Push: `git push origin master --tags`
6. The `release.yml` workflow runs CI, builds the wheel, and creates a GitHub Release with artifacts
7. Reinstall locally: `uv tool install -e . --force`

## Project Context

- CLI entry point: `cpf` (defined in `src/checkpointflow/cli.py`).
- Workflow definitions are YAML, validated against JSON schemas in `schemas/`.
- Runtime state stored in `~/.checkpointflow/`, separate from workflow files.
- Currently in Phase 1 development — see `checkpointflow-phase1-implementation-plan.md` for scope.
