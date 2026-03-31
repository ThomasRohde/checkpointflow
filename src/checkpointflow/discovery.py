"""Shared workflow discovery logic used by both CLI and GUI."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import yaml


class DiscoveredWorkflow(NamedTuple):
    """A workflow found during directory scanning."""

    name: str
    workflow_id: str
    description: str | None
    version: str | None
    path: Path


def discover_workflows(
    search_dirs: list[Path] | None = None,
) -> list[DiscoveredWorkflow]:
    """Find checkpointflow workflow YAML files in the given directories.

    Searches non-recursively for ``*.yaml`` and ``*.yml`` files, deduplicates
    by resolved path, and skips files that are unreadable or not valid
    checkpointflow workflows.

    If *search_dirs* is ``None``, searches ``cwd/.checkpointflow`` and
    ``~/.checkpointflow`` by default.
    """
    if search_dirs is None:
        search_dirs = [
            Path.cwd() / ".checkpointflow",
            Path.home() / ".checkpointflow",
        ]

    found: list[DiscoveredWorkflow] = []
    seen: set[Path] = set()

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for pattern in ("*.yaml", "*.yml"):
            for yaml_file in sorted(search_dir.glob(pattern)):
                resolved = yaml_file.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                try:
                    doc = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                except (yaml.YAMLError, OSError):
                    continue
                if not isinstance(doc, dict):
                    continue
                wf = doc.get("workflow")
                if not isinstance(wf, dict):
                    continue
                name = wf.get("name") or wf.get("id", yaml_file.stem)
                found.append(
                    DiscoveredWorkflow(
                        name=name,
                        workflow_id=wf.get("id", ""),
                        description=wf.get("description"),
                        version=wf.get("version"),
                        path=yaml_file,
                    )
                )

    return found
