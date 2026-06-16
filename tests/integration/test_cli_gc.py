from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from houba.cli.main import app

runner = CliRunner()


def _env(monkeypatch: pytest.MonkeyPatch, fake_bin_path: Path, log: Path) -> None:
    monkeypatch.setenv("PATH", f"{fake_bin_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv(
        "HOUBA_REGISTRIES",
        json.dumps({"harbor": {"host": "harbor.example", "tls_verify": False}}),
    )
    monkeypatch.setenv("HOUBA_LOG_FORMAT", "json")
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "gc-superseded")
    monkeypatch.setenv("FAKE_REGCTL_LOG", str(log))


def test_gc_dry_run_does_not_delete(
    monkeypatch: pytest.MonkeyPatch, fake_bin_path: Path, tmp_path: Path
) -> None:
    log = tmp_path / "regctl.log"
    _env(monkeypatch, fake_bin_path, log)
    result = runner.invoke(app, ["gc", "--keep", "1", "--older-than-days", "0"])
    assert result.exit_code == 0, result.stdout
    assert "dry-run" in result.stdout
    log_text = log.read_text() if log.exists() else ""
    assert "manifest delete" not in log_text


def test_gc_apply_deletes_the_older_referrer(
    monkeypatch: pytest.MonkeyPatch, fake_bin_path: Path, tmp_path: Path
) -> None:
    log = tmp_path / "regctl.log"
    _env(monkeypatch, fake_bin_path, log)
    result = runner.invoke(app, ["gc", "--keep", "1", "--older-than-days", "0", "--apply"])
    assert result.exit_code == 0, result.stdout
    log_text = log.read_text()
    assert "manifest delete harbor.example/lib/redis@sha256:old" in log_text
    assert "sha256:new" not in log_text.split("manifest delete", 1)[-1]  # newest kept
