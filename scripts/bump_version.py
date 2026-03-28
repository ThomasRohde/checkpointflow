"""Bump the version in pyproject.toml and print the new version as JSON."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
VERSION_RE = re.compile(r'^(version\s*=\s*")(\d+\.\d+\.\d+)(")', re.MULTILINE)


def bump(kind: str) -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    m = VERSION_RE.search(text)
    if not m:
        print(json.dumps({"error": "Could not find version in pyproject.toml"}))
        sys.exit(1)

    major, minor, patch = (int(x) for x in m.group(2).split("."))

    if kind == "major":
        major, minor, patch = major + 1, 0, 0
    elif kind == "minor":
        major, minor, patch = major, minor + 1, 0
    elif kind == "patch":
        major, minor, patch = major, minor, patch + 1
    else:
        print(json.dumps({"error": f"Unknown bump kind: {kind}"}))
        sys.exit(1)

    new_version = f"{major}.{minor}.{patch}"
    new_text = VERSION_RE.sub(rf"\g<1>{new_version}\3", text)
    PYPROJECT.write_text(new_text, encoding="utf-8")

    print(json.dumps({"version": new_version, "previous": m.group(2)}))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: bump_version.py [major|minor|patch]"}))
        sys.exit(1)
    bump(sys.argv[1])
