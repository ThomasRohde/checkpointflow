from __future__ import annotations

import json
import subprocess
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from checkpointflow.engine.evaluator import EvaluatorError, interpolate
from checkpointflow.models.errors import ErrorCode
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import CliStep


def _build_subprocess_args(command: str, shell: str | None) -> dict[str, Any]:
    """Build subprocess.run kwargs for the given shell."""
    if shell and shell.lower() in ("powershell", "pwsh", "powershell.exe", "pwsh.exe"):
        exe = "pwsh" if shell.lower() in ("pwsh", "pwsh.exe") else "powershell"
        return {
            "args": [exe, "-NoProfile", "-NonInteractive", "-Command", command],
            "shell": False,
        }
    if shell and shell.lower() not in ("bash", "sh", "cmd", "cmd.exe"):
        # Explicit shell: pass as executable
        return {"args": command, "shell": True, "executable": shell}
    # Default: system shell
    return {"args": command, "shell": True}


def execute(step: CliStep, ctx: RunContext) -> StepResult:
    # Build evaluator context
    eval_ctx: dict[str, Any] = {
        "inputs": ctx.inputs,
        "steps": {sid: {"outputs": outs} for sid, outs in ctx.step_outputs.items()},
    }

    # Resolve command expressions
    try:
        resolved_cmd = interpolate(step.command, eval_ctx)
    except EvaluatorError as exc:
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=f"Step '{step.id}' command interpolation failed: {exc}",
        )

    # Determine timeout
    timeout = step.timeout_seconds if step.timeout_seconds and step.timeout_seconds > 0 else None

    # Execute
    stdout_path = ctx.run_dir / "stdout" / f"{step.id}.txt"
    stderr_path = ctx.run_dir / "stderr" / f"{step.id}.txt"

    shell_args = _build_subprocess_args(resolved_cmd, step.shell)
    try:
        proc = subprocess.run(
            **shell_args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_TIMEOUT,
            error_message=f"Step '{step.id}' timed out after {timeout}s",
        )

    # Write captured output
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")

    # Check exit code
    success_codes = step.success.exit_codes if step.success and step.success.exit_codes else [0]
    if proc.returncode not in success_codes:
        return StepResult(
            success=False,
            exit_code=proc.returncode,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=(f"Step '{step.id}' exited with code {proc.returncode}"),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )

    # Try parsing stdout as JSON
    outputs: dict[str, Any] | None = None
    stdout_text = proc.stdout.strip()
    if stdout_text:
        try:
            parsed = json.loads(stdout_text)
            if isinstance(parsed, dict):
                outputs = parsed
        except json.JSONDecodeError:
            pass

    # Validate against output schema if defined
    if step.outputs is not None and outputs is None:
        return StepResult(
            success=False,
            exit_code=proc.returncode,
            error_code=ErrorCode.ERR_STEP_OUTPUT_INVALID,
            error_message=(
                f"Step '{step.id}' declares outputs schema but stdout is not valid JSON"
            ),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )
    if step.outputs is not None and outputs is not None:
        validator = Draft202012Validator(step.outputs)
        errors = [e.message for e in validator.iter_errors(outputs)]
        if errors:
            return StepResult(
                success=False,
                exit_code=proc.returncode,
                error_code=ErrorCode.ERR_STEP_OUTPUT_INVALID,
                error_message=(f"Step '{step.id}' output validation failed: {errors[0]}"),
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
            )

    return StepResult(
        success=True,
        outputs=outputs,
        exit_code=proc.returncode,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
    )
