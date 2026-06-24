from typer.testing import CliRunner

from houba.cli.main import app
from houba.errors import ConfigError, exit_code_for

runner = CliRunner()


def test_verify_in_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "verify" in result.stdout


def test_verify_bad_require_is_config_error_mapped_to_exit_3(monkeypatch):
    monkeypatch.setenv("HOUBA_ATTEST_SIGNER", "key")
    monkeypatch.setenv("HOUBA_ATTEST_KEY_REF", "/tmp/cosign.pub")
    result = runner.invoke(app, ["verify", "reg/app@sha256:" + "a" * 64, "--require", "bogus"])
    # CliRunner bypasses main._run's exception->exit-code mapping, so the ConfigError
    # surfaces as result.exception. Assert the real product contract directly: the command
    # raises ConfigError and the entry-point wrapper maps it to exit 3.
    assert isinstance(result.exception, ConfigError)
    assert exit_code_for(result.exception) == 3
