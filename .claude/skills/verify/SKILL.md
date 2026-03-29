---
name: verify
description: Run the full quality gate — formatting, linting, type checking, and tests. Use after implementing changes to confirm everything passes.
---

Run the complete quality gate for this project. Execute each step sequentially and report results:

1. `uv run ruff format --check .` — verify formatting
2. `uv run ruff check .` — lint
3. `uv run mypy` — strict type checking
4. `uv run pytest` — run all tests

If any step fails, stop and report the failure with details. If all pass, confirm the change is ready.
