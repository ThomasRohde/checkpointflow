"""Input parsing utilities for workflow runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_input(raw: str) -> dict[str, Any]:
    """Parse input from inline JSON or @file reference."""
    if raw.startswith("@"):
        file_path = Path(raw[1:])
        # Block path traversal sequences
        if ".." in file_path.parts:
            msg = f"Path traversal not allowed in input file path: {file_path}"
            raise ValueError(msg)
        if not file_path.exists():
            msg = f"Input file not found: {file_path}"
            raise FileNotFoundError(msg)
        return json.loads(file_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    return json.loads(raw)  # type: ignore[no-any-return]
