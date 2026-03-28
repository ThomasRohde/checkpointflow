"""Print the current version from pyproject.toml as JSON."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def main() -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', text, re.MULTILINE)
    if not m:
        print(json.dumps({"error": "Could not find version"}))
        sys.exit(1)
    print(json.dumps({"version": m.group(1)}))


if __name__ == "__main__":
    main()
