from __future__ import annotations

import contextlib
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from checkpointflow.engine.evaluator import EvaluatorError, interpolate
from checkpointflow.models.errors import ErrorCode
from checkpointflow.models.state import RunContext, StepResult
from checkpointflow.models.workflow import ApiStep


def execute(step: ApiStep, ctx: RunContext) -> StepResult:
    """Execute an HTTP request and return the response as outputs."""
    eval_ctx = ctx.build_eval_context()

    # Interpolate URL
    try:
        url = interpolate(step.url, eval_ctx) if "${" in step.url else step.url
    except EvaluatorError as exc:
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=f"Step '{step.id}' URL interpolation failed: {exc}",
        )

    # Validate URL scheme
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme not in ("http", "https"):
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=(
                f"Step '{step.id}' URL has unsupported scheme '{parsed_url.scheme}'. "
                f"Only http and https are allowed."
            ),
        )

    # Build request body
    data: bytes | None = None
    if step.body is not None:
        body_value = step.body
        if isinstance(body_value, str) and "${" in body_value:
            try:
                body_value = interpolate(body_value, eval_ctx)
            except EvaluatorError as exc:
                return StepResult(
                    success=False,
                    error_code=ErrorCode.ERR_STEP_FAILED,
                    error_message=f"Step '{step.id}' body interpolation failed: {exc}",
                )
        data = json.dumps(body_value).encode("utf-8")

    # Build headers
    headers: dict[str, str] = {}
    if step.headers:
        for k, v in step.headers.items():
            val = str(v)
            if "${" in val:
                with contextlib.suppress(EvaluatorError):
                    val = interpolate(val, eval_ctx)
            headers[k] = val
    if data is not None and "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"

    # Execute request
    req = urllib.request.Request(url, data=data, headers=headers, method=step.method)
    try:
        timeout = step.timeout_seconds if step.timeout_seconds and step.timeout_seconds > 0 else 30
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code: int = resp.status
            resp_body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        resp_body = exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return StepResult(
            success=False,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=f"Step '{step.id}' request failed: {exc}",
        )

    # Write response to artifacts
    stdout_path = ctx.run_dir / "stdout" / f"{step.id}.txt"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(resp_body, encoding="utf-8")

    # Check status code
    success_codes = (
        step.success.status_codes if step.success and step.success.status_codes else [200, 201, 204]
    )
    if status_code not in success_codes:
        return StepResult(
            success=False,
            exit_code=status_code,
            error_code=ErrorCode.ERR_STEP_FAILED,
            error_message=f"Step '{step.id}' returned status {status_code}",
            stdout_path=str(stdout_path),
        )

    # Parse response as JSON if possible
    outputs: dict[str, Any] | None = None
    if resp_body.strip():
        try:
            parsed = json.loads(resp_body)
            outputs = parsed if isinstance(parsed, dict) else {"body": parsed}
        except json.JSONDecodeError:
            outputs = {"body": resp_body}

    return StepResult(
        success=True,
        outputs=outputs,
        exit_code=status_code,
        stdout_path=str(stdout_path),
    )
