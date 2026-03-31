from typer.testing import CliRunner

from checkpointflow import __version__
from checkpointflow.cli import app


def test_help_smoke() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "checkpointflow" in result.stdout


def test_version_flag() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.stdout
