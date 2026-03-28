from __future__ import annotations

from typing import Annotated

import typer

from checkpointflow import __version__

app = typer.Typer(
    name="cpf",
    help=(
        "checkpointflow CLI scaffolding. Phase 1 will add validate, run, resume, "
        "status, inspect, guide, init, and cancel."
    ),
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


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
            help="Show the installed checkpointflow version.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    del version


def main() -> None:
    app()
