from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer
import yaml

if TYPE_CHECKING:
    from checkpointflow.discovery import DiscoveredWorkflow

from checkpointflow import __version__
from checkpointflow.models.envelope import Envelope
from checkpointflow.models.errors import ErrorCode, ExitCode
from checkpointflow.schema import validate_workflow_document

app = typer.Typer(
    name="cpf",
    help="checkpointflow — deterministic, resumable agent workflows.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _emit(envelope: Envelope) -> NoReturn:
    typer.echo(envelope.to_json())
    raise typer.Exit(code=envelope.exit_code or 0)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            help="Show the installed checkpointflow version.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    del version


@app.command()
def validate(
    file: Annotated[
        Path,
        typer.Option("-f", "--file", help="Path to workflow YAML file."),
    ],
) -> None:
    """Validate a workflow YAML file against the checkpointflow schema."""
    try:
        if not file.exists():
            _emit(
                Envelope.failure(
                    command="validate",
                    error_code=ErrorCode.ERR_FILE_NOT_FOUND,
                    message=f"Workflow file not found: {file}",
                    exit_code=ExitCode.VALIDATION_ERROR,
                )
            )

        if file.is_dir():
            _emit(
                Envelope.failure(
                    command="validate",
                    error_code=ErrorCode.ERR_VALIDATION_WORKFLOW,
                    message=f"Expected a file, got a directory: {file}",
                    exit_code=ExitCode.VALIDATION_ERROR,
                )
            )

        try:
            with file.open() as f:
                doc = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            _emit(
                Envelope.failure(
                    command="validate",
                    error_code=ErrorCode.ERR_YAML_PARSE,
                    message=f"YAML parse error: {exc}",
                    exit_code=ExitCode.VALIDATION_ERROR,
                )
            )

        errors = validate_workflow_document(doc)
        if errors:
            _emit(
                Envelope.failure(
                    command="validate",
                    error_code=ErrorCode.ERR_VALIDATION_WORKFLOW,
                    message=f"Workflow validation failed with {len(errors)} error(s).",
                    exit_code=ExitCode.VALIDATION_ERROR,
                    details=errors,
                )
            )

        # Check for duplicate step IDs
        workflow = doc["workflow"]
        step_ids = [s["id"] for s in workflow.get("steps", [])]
        seen: set[str] = set()
        duplicates = []
        for sid in step_ids:
            if sid in seen:
                duplicates.append(sid)
            seen.add(sid)
        if duplicates:
            _emit(
                Envelope.failure(
                    command="validate",
                    error_code=ErrorCode.ERR_DUPLICATE_STEP_ID,
                    message=f"Duplicate step ID(s): {', '.join(duplicates)}",
                    exit_code=ExitCode.VALIDATION_ERROR,
                )
            )

        _emit(
            Envelope.success(
                command="validate",
                workflow_id=workflow["id"],
                workflow_version=workflow.get("version"),
            )
        )
    except typer.Exit:
        raise
    except Exception as exc:
        _emit(
            Envelope.failure(
                command="validate",
                error_code=ErrorCode.ERR_INTERNAL,
                message=f"Internal error: {exc}",
                exit_code=ExitCode.INTERNAL_ERROR,
            )
        )


@app.command()
def run(
    file: Annotated[
        Path,
        typer.Option("-f", "--file", help="Path to workflow YAML file."),
    ],
    input_data: Annotated[
        str,
        typer.Option("--input", help="Input JSON (inline, @file path, or - for stdin)."),
    ] = "{}",
) -> None:
    """Run a workflow from start to completion or next wait point."""
    import sys

    from checkpointflow.engine.runner import run_workflow

    raw = sys.stdin.read() if input_data == "-" else input_data
    envelope = run_workflow(file, raw, base_dir=_get_base_dir())
    _emit(envelope)


def _get_base_dir() -> Path | None:
    import os

    base_dir_str = os.environ.get("CHECKPOINTFLOW_BASE_DIR")
    return Path(base_dir_str) if base_dir_str else None


@app.command()
def resume(
    run_id: Annotated[
        str,
        typer.Option("--run-id", help="Run ID to resume."),
    ],
    event: Annotated[
        str,
        typer.Option("--event", help="Event name."),
    ],
    input_data: Annotated[
        str,
        typer.Option("--input", help="Event input JSON (inline, @file, or - for stdin)."),
    ],
) -> None:
    """Resume a waiting run with an event payload."""
    import sys

    from checkpointflow.engine.runner import resume_workflow

    raw = sys.stdin.read() if input_data == "-" else input_data
    envelope = resume_workflow(run_id, event, raw, base_dir=_get_base_dir())
    _emit(envelope)


@app.command()
def status(
    run_id: Annotated[
        str,
        typer.Option("--run-id", help="Run ID to query."),
    ],
) -> None:
    """Query the current status of a run."""
    from checkpointflow.engine.queries import query_status

    envelope = query_status(run_id, base_dir=_get_base_dir())
    _emit(envelope)


@app.command()
def inspect(
    run_id: Annotated[
        str,
        typer.Option("--run-id", help="Run ID to inspect."),
    ],
) -> None:
    """Inspect detailed execution history and state of a run."""
    from checkpointflow.engine.queries import query_inspect

    envelope = query_inspect(run_id, base_dir=_get_base_dir())
    _emit(envelope)


_INIT_TEMPLATE = """\
schema_version: checkpointflow/v1
workflow:
  id: my_workflow
  name: My Workflow
  version: 0.1.0

  defaults:
    shell: bash

  inputs:
    type: object
    required: [name]
    properties:
      name:
        type: string

  steps:
    - id: greet
      kind: cli
      command: echo "Hello, ${inputs.name}"

    - id: done
      kind: end
      result:
        status: completed
"""


@app.command()
def guide() -> None:
    """Print the checkpointflow user guide."""
    import importlib.resources

    guide_file = importlib.resources.files("checkpointflow.docs").joinpath("guide.md")
    typer.echo(guide_file.read_text(encoding="utf-8"))


@app.command()
def init(
    file: Annotated[
        Path,
        typer.Option("--file", help="Output path for the workflow file."),
    ] = Path("checkpointflow.yaml"),
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing file."),
    ] = False,
) -> None:
    """Scaffold a new workflow YAML file."""
    if file.exists() and not force:
        _emit(
            Envelope.failure(
                command="init",
                error_code=ErrorCode.ERR_FILE_EXISTS,
                message=f"File already exists: {file}. Use --force to overwrite.",
                exit_code=ExitCode.VALIDATION_ERROR,
            )
        )
    try:
        file.write_text(_INIT_TEMPLATE)
    except OSError as exc:
        _emit(
            Envelope.failure(
                command="init",
                error_code=ErrorCode.ERR_PERSISTENCE,
                message=f"Failed to write file: {exc}",
                exit_code=ExitCode.PERSISTENCE_ERROR,
            )
        )
    _emit(
        Envelope.success(
            command="init",
            result={"file": str(file)},
        )
    )


@app.command()
def cancel(
    run_id: Annotated[
        str,
        typer.Option("--run-id", help="Run ID to cancel."),
    ],
    reason: Annotated[
        str,
        typer.Option("--reason", help="Reason for cancellation."),
    ],
) -> None:
    """Cancel a waiting or running run."""
    from checkpointflow.engine.runner import cancel_run

    envelope = cancel_run(run_id, reason, base_dir=_get_base_dir())
    _emit(envelope)


@app.command()
def delete(
    run_id: Annotated[
        str,
        typer.Option("--run-id", help="Run ID to delete."),
    ],
) -> None:
    """Permanently delete a completed, failed, or cancelled run."""
    from checkpointflow.engine.runner import delete_run

    envelope = delete_run(run_id, base_dir=_get_base_dir())
    _emit(envelope)


@app.command()
def gui(
    port: Annotated[
        int,
        typer.Option(help="Port to serve on."),
    ] = 8420,
) -> None:
    """Launch the checkpointflow web dashboard."""
    from checkpointflow.gui.server import run_server

    run_server(port=port, base_dir=_get_base_dir())


def _print_flow_detail(match: DiscoveredWorkflow) -> None:
    """Print comprehensive flow details so an agent can run it without reading source."""
    import json

    # Identity
    typer.echo(f"id: {match.workflow_id}" if match.workflow_id else f"name: {match.name}")
    if match.workflow_id:
        typer.echo(f"name: {match.name}")
    if match.version:
        typer.echo(f"version: {match.version}")
    if match.description:
        typer.echo(f"description: {match.description.strip()}")

    # Load the full YAML for inputs and steps
    try:
        doc = yaml.safe_load(match.path.read_text(encoding="utf-8"))
        wf = doc.get("workflow", {})
    except Exception:
        typer.echo(f"\nrun: cpf run -f {match.path}")
        return

    # Inputs
    inputs_schema = wf.get("inputs", {})
    properties = inputs_schema.get("properties", {})
    required_keys = set(inputs_schema.get("required", []))
    if properties:
        typer.echo("\ninputs:")
        for key, prop in properties.items():
            tag = " (required)" if key in required_keys else ""
            prop_type = prop.get("type", "string")
            desc = prop.get("description", "").strip()
            enum_vals = prop.get("enum")
            line = f"  {key}{tag}: {prop_type}"
            if enum_vals:
                line += f" — one of: {', '.join(str(v) for v in enum_vals)}"
            if desc:
                line += f" — {desc}"
            typer.echo(line)

    # Steps overview
    steps = wf.get("steps", [])
    non_end_steps = [s for s in steps if s.get("kind") != "end"]
    if non_end_steps:
        typer.echo("\nsteps:")
        for step in non_end_steps:
            step_id = step.get("id", "?")
            kind = step.get("kind", "?")
            name = step.get("name", "")
            audience = step.get("audience", "")
            parts = [f"  {step_id}: {kind}"]
            if name:
                parts.append(f'"{name}"')
            if audience:
                parts.append(f"[{audience}]")
            typer.echo(" ".join(parts))

    # Run command with input template (required inputs only, short placeholders)
    input_template: dict[str, str] = {}
    for key in properties:
        if key in required_keys:
            input_template[key] = f"<{key}>"
    typer.echo(f"\nrun: cpf run -f {match.path} --input '{json.dumps(input_template)}'")


@app.command()
def flows(
    detail: Annotated[
        str | None,
        typer.Option("--detail", help="Show details for a specific workflow (by id or name)."),
    ] = None,
) -> None:
    """List available workflows, or show details for one."""
    from checkpointflow.discovery import discover_workflows

    found = discover_workflows()

    if not found:
        typer.echo("No workflows found.")
        raise typer.Exit()

    if detail is not None:
        query = detail.lower()
        match = next(
            (wf for wf in found if wf.workflow_id.lower() == query or wf.name.lower() == query),
            None,
        )
        if match is None:
            typer.echo(f'No workflow matching "{detail}".')
            raise typer.Exit(code=1)
        _print_flow_detail(match)
    else:
        for wf in found:
            typer.echo(f"- id: {wf.workflow_id}" if wf.workflow_id else f"- name: {wf.name}")
            if wf.workflow_id:
                typer.echo(f"  name: {wf.name}")
        typer.echo("")
        typer.echo("Show details: cpf flows --detail <id>")
        typer.echo("Run a flow:   cpf run <id>")


def main() -> None:
    app()
