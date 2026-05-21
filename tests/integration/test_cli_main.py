from typer.testing import CliRunner

from hub2hub.cli.main import app


def test_h2h_version_outputs_version_string() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_h2h_help_lists_subgroups() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "dev" in result.stdout
    assert "version" in result.stdout
