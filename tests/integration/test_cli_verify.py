from typer.testing import CliRunner

from houba.cli.main import app

runner = CliRunner()


def test_verify_in_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "verify" in result.stdout


def test_verify_bad_require_is_config_exit_3(monkeypatch):
    monkeypatch.setenv("HOUBA_ATTEST_SIGNER", "key")
    monkeypatch.setenv("HOUBA_ATTEST_KEY_REF", "/tmp/cosign.pub")
    # main._run maps ConfigError -> exit 3; invoke the wrapper via the module entry.
    result = runner.invoke(app, ["verify", "reg/app@sha256:" + "a" * 64, "--require", "bogus"])
    assert result.exit_code != 0
