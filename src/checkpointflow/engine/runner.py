from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from checkpointflow.engine.evaluator import EvaluatorError, evaluate_condition
from checkpointflow.engine.steps import await_event_step, cli_step, end_step
from checkpointflow.models.envelope import Envelope, WaitDetail, WaitResume
from checkpointflow.models.errors import ErrorCode, ExitCode
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import (
    AwaitEventStep,
    CliStep,
    EndStep,
    Workflow,
    WorkflowDocument,
)
from checkpointflow.persistence.store import PersistenceError, Store
from checkpointflow.schema import validate_workflow_document

Step = CliStep | AwaitEventStep | EndStep


class RunError(Exception):
    pass


def _parse_input(raw: str) -> dict[str, Any]:
    """Parse input from inline JSON or @file reference."""
    if raw.startswith("@"):
        file_path = Path(raw[1:])
        if not file_path.exists():
            msg = f"Input file not found: {file_path}"
            raise FileNotFoundError(msg)
        return json.loads(file_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    return json.loads(raw)  # type: ignore[no-any-return]


def _build_wait_detail(
    step: AwaitEventStep,
    run_id: str,
    eval_ctx: dict[str, Any] | None = None,
) -> WaitDetail:
    """Build WaitDetail for awaiting step."""
    from checkpointflow.engine.evaluator import interpolate as _interpolate

    resume_cmd = f"cpf resume --run-id {run_id} --event {step.event_name} --input @event.json"
    prompt = step.prompt
    summary = step.summary
    if eval_ctx:
        if prompt and "${" in prompt:
            prompt = _interpolate(prompt, eval_ctx)
        if summary and "${" in summary:
            summary = _interpolate(summary, eval_ctx)
    return WaitDetail(
        audience=step.audience,
        event_name=step.event_name,
        prompt=prompt,
        summary=summary,
        input_schema=step.input_schema,
        instructions=[
            "Ask the intended audience for input using the prompt.",
            "Collect JSON that matches input_schema.",
            "Resume with the provided run_id and event_name.",
        ],
        risk_level=step.risk_level,
        resume=WaitResume(command=resume_cmd),
    )


def _strip_expression_wrapper(expr: str) -> str:
    """Strip ${...} wrapper from an expression string."""
    if expr.startswith("${") and expr.endswith("}"):
        return expr[2:-1]
    return expr


def _build_eval_context(
    inputs: dict[str, Any],
    step_outputs: dict[str, dict[str, Any]],
    event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build evaluation context for expressions."""
    ctx: dict[str, Any] = {
        "inputs": inputs,
        "steps": {sid: {"outputs": outs} for sid, outs in step_outputs.items()},
    }
    if event is not None:
        ctx["event"] = event
    return ctx


def _execute_steps(
    workflow: Workflow,
    store: Store,
    run_id: str,
    run_dir: Path,
    inputs: dict[str, Any],
    step_outputs: dict[str, dict[str, Any]],
    steps: list[Any],
    start_order: int,
    command: str,
) -> Envelope:
    """Execute a sequence of steps, returning an envelope on halt or completion."""
    for i, step in enumerate(steps):
        order = start_order + i

        # Check if condition
        if step.step_if:
            condition = _strip_expression_wrapper(step.step_if)
            eval_ctx = _build_eval_context(inputs, step_outputs)
            try:
                if not evaluate_condition(condition, eval_ctx):
                    continue
            except EvaluatorError:
                continue

        # Update run status
        with contextlib.suppress(PersistenceError):
            store.update_run(run_id, status="running", current_step_id=step.id)

        ctx = RunContext(
            run_id=run_id,
            inputs=inputs,
            step_outputs=step_outputs,
            run_dir=run_dir,
            defaults=workflow.defaults or {},
        )

        # Dispatch step handler
        if isinstance(step, CliStep):
            result = cli_step.execute(step, ctx)
        elif isinstance(step, EndStep):
            result = end_step.execute(step, ctx)
        elif isinstance(step, AwaitEventStep):
            result = await_event_step.execute(step, ctx)
        else:
            store.update_run(run_id, status="failed")
            return Envelope.failure(
                command=command,
                error_code=ErrorCode.ERR_UNSUPPORTED_STEP,
                message=f"Step kind '{step.kind}' is not supported in this version.",
                exit_code=ExitCode.UNSUPPORTED,
                run_id=run_id,
                workflow_id=workflow.id,
                workflow_version=workflow.version,
            )

        # Persist step result
        store.insert_step_result(
            run_id=run_id,
            step_id=step.id,
            step_kind=step.kind,
            execution_order=order,
            exit_code=result.exit_code,
            stdout_path=result.stdout_path,
            stderr_path=result.stderr_path,
            outputs_json=json.dumps(result.outputs) if result.outputs else None,
            error_code=result.error_code,
            error_message=result.error_message,
        )

        if not result.success:
            store.update_run(run_id, status="failed")
            return Envelope.failure(
                command=command,
                error_code=result.error_code or ErrorCode.ERR_STEP_FAILED,
                message=result.error_message or f"Step '{step.id}' failed",
                exit_code=ExitCode.STEP_FAILED,
                run_id=run_id,
                workflow_id=workflow.id,
                workflow_version=workflow.version,
                current_step_id=step.id,
            )

        # Merge outputs
        if result.outputs is not None:
            step_outputs[step.id] = result.outputs

        # Store accumulated outputs
        store.update_run(run_id, step_outputs_json=json.dumps(step_outputs))

        # AwaitEventStep: halt and return waiting envelope
        if isinstance(step, AwaitEventStep):
            store.update_run(
                run_id,
                status="waiting",
                current_step_id=step.id,
                expected_event_name=step.event_name,
                expected_event_schema=json.dumps(step.input_schema),
            )
            wait_eval_ctx = _build_eval_context(inputs, step_outputs)
            wait_detail = _build_wait_detail(step, run_id, eval_ctx=wait_eval_ctx)
            return Envelope.success(
                command=command,
                status="waiting",
                exit_code=ExitCode.WAITING,
                run_id=run_id,
                workflow_id=workflow.id,
                workflow_version=workflow.version,
                current_step_id=step.id,
                wait=wait_detail,
            )

        # EndStep: terminate workflow
        if isinstance(step, EndStep):
            final_result = result.outputs if result.outputs else {}
            store.update_run(
                run_id,
                status="completed",
                result_json=json.dumps(final_result),
            )
            return Envelope.success(
                command=command,
                run_id=run_id,
                workflow_id=workflow.id,
                workflow_version=workflow.version,
                current_step_id=step.id,
                result=final_result if final_result else None,
            )

    # Implicit completion (no explicit end step)
    store.update_run(run_id, status="completed")
    return Envelope.success(
        command=command,
        run_id=run_id,
        workflow_id=workflow.id,
        workflow_version=workflow.version,
    )


# --- run_workflow ---


def run_workflow(
    workflow_path: Path,
    input_raw: str,
    *,
    base_dir: Path | None = None,
) -> Envelope:
    """Execute a workflow and return an envelope with the result."""
    try:
        return _run_workflow_inner(workflow_path, input_raw, base_dir=base_dir)
    except Exception as exc:
        return Envelope.failure(
            command="run",
            error_code=ErrorCode.ERR_INTERNAL,
            message=f"Internal error: {exc}",
            exit_code=ExitCode.INTERNAL_ERROR,
        )


def _run_workflow_inner(
    workflow_path: Path,
    input_raw: str,
    *,
    base_dir: Path | None = None,
) -> Envelope:
    # --- Load and validate workflow ---
    if not workflow_path.exists():
        return Envelope.failure(
            command="run",
            error_code=ErrorCode.ERR_FILE_NOT_FOUND,
            message=f"Workflow file not found: {workflow_path}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    raw_text = workflow_path.read_text(encoding="utf-8")
    try:
        doc_dict = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        return Envelope.failure(
            command="run",
            error_code=ErrorCode.ERR_YAML_PARSE,
            message=f"YAML parse error: {exc}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    schema_errors = validate_workflow_document(doc_dict)
    if schema_errors:
        return Envelope.failure(
            command="run",
            error_code=ErrorCode.ERR_VALIDATION_WORKFLOW,
            message=f"Workflow validation failed with {len(schema_errors)} error(s).",
            exit_code=ExitCode.VALIDATION_ERROR,
            details=schema_errors,
        )

    doc = WorkflowDocument.model_validate(doc_dict)
    workflow = doc.workflow

    # --- Parse and validate input ---
    try:
        inputs = _parse_input(input_raw)
    except FileNotFoundError as exc:
        return Envelope.failure(
            command="run",
            error_code=ErrorCode.ERR_FILE_NOT_FOUND,
            message=str(exc),
            exit_code=ExitCode.VALIDATION_ERROR,
        )
    except (json.JSONDecodeError, TypeError) as exc:
        return Envelope.failure(
            command="run",
            error_code=ErrorCode.ERR_VALIDATION_INPUT,
            message=f"Invalid input JSON: {exc}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    # Validate input against workflow schema
    input_validator = Draft202012Validator(workflow.inputs)
    input_errors = [e.message for e in input_validator.iter_errors(inputs)]
    if input_errors:
        return Envelope.failure(
            command="run",
            error_code=ErrorCode.ERR_VALIDATION_INPUT,
            message=f"Input validation failed: {input_errors[0]}",
            exit_code=ExitCode.VALIDATION_ERROR,
            details=input_errors,
        )

    # --- Initialize persistence ---
    try:
        store = Store(base_dir=base_dir)
    except Exception as exc:
        return Envelope.failure(
            command="run",
            error_code=ErrorCode.ERR_PERSISTENCE,
            message=f"Failed to initialize store: {exc}",
            exit_code=ExitCode.PERSISTENCE_ERROR,
        )

    workflow_hash = hashlib.sha256(raw_text.encode()).hexdigest()
    run_id = store.create_run(
        workflow_id=workflow.id,
        workflow_version=workflow.version,
        workflow_hash=workflow_hash,
        workflow_path=str(workflow_path.resolve()),
        inputs_json=json.dumps(inputs),
    )

    run_dir = store.run_dir(run_id)
    return _execute_steps(
        workflow, store, run_id, run_dir, inputs, {}, list(workflow.steps), 0, "run"
    )


# --- resume_workflow ---


def resume_workflow(
    run_id: str,
    event_name: str,
    event_input_raw: str,
    *,
    base_dir: Path | None = None,
) -> Envelope:
    """Resume a waiting run with an event payload."""
    try:
        return _resume_workflow_inner(run_id, event_name, event_input_raw, base_dir=base_dir)
    except Exception as exc:
        return Envelope.failure(
            command="resume",
            error_code=ErrorCode.ERR_INTERNAL,
            message=f"Internal error: {exc}",
            exit_code=ExitCode.INTERNAL_ERROR,
            run_id=run_id,
        )


def _resume_workflow_inner(
    run_id: str,
    event_name: str,
    event_input_raw: str,
    *,
    base_dir: Path | None = None,
) -> Envelope:
    store = Store(base_dir=base_dir)
    run = store.get_run(run_id)

    # Verify run exists
    if run is None:
        return Envelope.failure(
            command="resume",
            error_code=ErrorCode.ERR_RUN_NOT_FOUND,
            message=f"Run not found: {run_id}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    # Verify waiting state
    if run["status"] != "waiting":
        return Envelope.failure(
            command="resume",
            error_code=ErrorCode.ERR_RUN_NOT_WAITING,
            message=f"Run {run_id} is not waiting (status: {run['status']})",
            exit_code=ExitCode.RUNTIME_ERROR,
            run_id=run_id,
        )

    # Verify event name
    if event_name != run["expected_event_name"]:
        return Envelope.failure(
            command="resume",
            error_code=ErrorCode.ERR_RESUME_EVENT_MISMATCH,
            message=(f"Expected event '{run['expected_event_name']}', got '{event_name}'"),
            exit_code=ExitCode.RUNTIME_ERROR,
            run_id=run_id,
        )

    # Parse event input
    try:
        event_data = _parse_input(event_input_raw)
    except FileNotFoundError as exc:
        return Envelope.failure(
            command="resume",
            error_code=ErrorCode.ERR_FILE_NOT_FOUND,
            message=str(exc),
            exit_code=ExitCode.VALIDATION_ERROR,
            run_id=run_id,
        )
    except (json.JSONDecodeError, TypeError) as exc:
        return Envelope.failure(
            command="resume",
            error_code=ErrorCode.ERR_VALIDATION_EVENT_INPUT,
            message=f"Invalid event JSON: {exc}",
            exit_code=ExitCode.VALIDATION_ERROR,
            run_id=run_id,
        )

    # Validate event against schema
    expected_schema = json.loads(run["expected_event_schema"])
    event_validator = Draft202012Validator(expected_schema)
    event_errors = [e.message for e in event_validator.iter_errors(event_data)]
    if event_errors:
        return Envelope.failure(
            command="resume",
            error_code=ErrorCode.ERR_VALIDATION_EVENT_INPUT,
            message=f"Event validation failed: {event_errors[0]}",
            exit_code=ExitCode.VALIDATION_ERROR,
            run_id=run_id,
            details=event_errors,
        )

    # Record event
    store.insert_event(
        run_id=run_id,
        event_name=event_name,
        event_json=json.dumps(event_data),
    )

    # Reload workflow
    workflow_path = Path(run["workflow_path"])
    if not workflow_path.exists():
        return Envelope.failure(
            command="resume",
            error_code=ErrorCode.ERR_FILE_NOT_FOUND,
            message=f"Workflow file not found: {workflow_path}",
            exit_code=ExitCode.VALIDATION_ERROR,
            run_id=run_id,
        )
    raw_text = workflow_path.read_text(encoding="utf-8")
    doc = WorkflowDocument.model_validate(yaml.safe_load(raw_text))
    workflow = doc.workflow

    # Restore state
    inputs: dict[str, Any] = json.loads(run["inputs_json"])
    step_outputs: dict[str, dict[str, Any]] = json.loads(run["step_outputs_json"])
    current_step_id = run["current_step_id"]

    # Store event data as the await_event step's outputs
    step_outputs[current_step_id] = event_data

    # Find current await_event step and determine next step
    step_ids = [s.id for s in workflow.steps]
    await_idx = step_ids.index(current_step_id)
    await_step = workflow.steps[await_idx]

    # Evaluate transitions
    next_step_id: str | None = None
    if isinstance(await_step, AwaitEventStep) and await_step.transitions:
        eval_ctx = _build_eval_context(inputs, step_outputs, event=event_data)
        for transition in await_step.transitions:
            condition = _strip_expression_wrapper(transition.when)
            try:
                if evaluate_condition(condition, eval_ctx):
                    next_step_id = transition.next
                    break
            except EvaluatorError:
                continue

        if next_step_id is None:
            return Envelope.failure(
                command="resume",
                error_code=ErrorCode.ERR_STEP_FAILED,
                message="No transition matched the event data.",
                exit_code=ExitCode.STEP_FAILED,
                run_id=run_id,
                current_step_id=current_step_id,
            )
    else:
        # No transitions: proceed to next step in array
        next_step_id = step_ids[await_idx + 1] if await_idx + 1 < len(step_ids) else None

    if next_step_id is None:
        store.update_run(run_id, status="completed")
        return Envelope.success(
            command="resume",
            run_id=run_id,
            workflow_id=workflow.id,
            workflow_version=workflow.version,
        )

    # Find target step index and execute from there
    target_idx = step_ids.index(next_step_id)
    remaining_steps = list(workflow.steps[target_idx:])
    run_dir = store.run_dir(run_id)
    existing_results = store.get_step_results(run_id)
    start_order = len(existing_results)

    # Update accumulated outputs with event data
    store.update_run(run_id, step_outputs_json=json.dumps(step_outputs))

    return _execute_steps(
        workflow,
        store,
        run_id,
        run_dir,
        inputs,
        step_outputs,
        remaining_steps,
        start_order,
        "resume",
    )


# --- cancel_run ---


def cancel_run(
    run_id: str,
    reason: str,
    *,
    base_dir: Path | None = None,
) -> Envelope:
    """Cancel a waiting or running run."""
    store = Store(base_dir=base_dir)
    run = store.get_run(run_id)

    if run is None:
        return Envelope.failure(
            command="cancel",
            error_code=ErrorCode.ERR_RUN_NOT_FOUND,
            message=f"Run not found: {run_id}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    if run["status"] not in ("waiting", "running", "created"):
        return Envelope.failure(
            command="cancel",
            error_code=ErrorCode.ERR_RUN_NOT_WAITING,
            message=f"Run {run_id} cannot be cancelled (status: {run['status']})",
            exit_code=ExitCode.RUNTIME_ERROR,
            run_id=run_id,
        )

    store.update_run(run_id, status="cancelled")
    return Envelope.success(
        command="cancel",
        status="cancelled",
        exit_code=ExitCode.SUCCESS,
        run_id=run_id,
        workflow_id=run["workflow_id"],
        workflow_version=run["workflow_version"],
        result={"reason": reason},
    )
