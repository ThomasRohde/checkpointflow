from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RunContext:
    run_id: str
    inputs: dict[str, Any]
    step_outputs: dict[str, dict[str, Any]]
    run_dir: Path
    defaults: dict[str, Any] = field(default_factory=dict)

    def build_eval_context(self) -> dict[str, Any]:
        """Build the evaluation context dict for expression interpolation."""
        return {
            "inputs": self.inputs,
            "steps": {sid: {"outputs": outs} for sid, outs in self.step_outputs.items()},
        }


@dataclass
class StepResult:
    success: bool
    outputs: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    exit_code: int | None = None
    stdout_path: str | None = field(default=None, repr=False)
    stderr_path: str | None = field(default=None, repr=False)
