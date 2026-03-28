from typer.testing import CliRunner

from checkpointflow.cli import app


def test_help_smoke() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "checkpointflow" in result.stdout
