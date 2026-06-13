from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from houba.cli.main import _run, app

runner = CliRunner()


def _env(monkeypatch: pytest.MonkeyPatch, fake_bin_path: Path) -> None:
    monkeypatch.setenv("PATH", f"{fake_bin_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv(
        "HOUBA_REGISTRIES", json.dumps({"harbor": {"host": "harbor.example", "tls_verify": False}})
    )
    monkeypatch.setenv("HOUBA_USAGE_ORACLE_CMD", str(fake_bin_path / "oracle"))
    monkeypatch.setenv("HOUBA_PURGE_MIN_IDLE_DAYS", "15")
    monkeypatch.setenv("HOUBA_LOG_FORMAT", "json")


def test_purge_missing_oracle_cmd_exits_3(
    monkeypatch: pytest.MonkeyPatch, fake_bin_path: Path
) -> None:
    # ConfigError → exit 3 is mapped in _run (not app), so drive _run with argv set
    # (mirrors tests/integration/test_cli_main.py's _run-based exit-code tests).
    _env(monkeypatch, fake_bin_path)
    monkeypatch.delenv("HOUBA_USAGE_ORACLE_CMD", raising=False)
    monkeypatch.setattr("sys.argv", ["houba", "purge"])
    with pytest.raises(SystemExit) as excinfo:
        _run()
    assert excinfo.value.code == 3


def test_purge_dry_run_reports_without_deleting(
    monkeypatch: pytest.MonkeyPatch, fake_bin_path: Path
) -> None:
    # 'repos' lists repos; default tag-ls returns a tag; 'artifact list' default returns
    # zero referrers ⇒ zero candidates ⇒ exit 0, dry-run summary.
    _env(monkeypatch, fake_bin_path)
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "repos")
    monkeypatch.setenv("FAKE_ORACLE_SCENARIO", "not-seen")
    result = runner.invoke(app, ["purge"])  # no --apply ⇒ dry-run
    assert result.exit_code == 0, result.stdout
    assert "dry-run" in result.stdout
