from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from houba.cli.main import app
from houba.errors import UnknownFormatError

SARIF = json.dumps(
    {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{"tool": {"driver": {"name": "trivy", "version": "0.50.1"}}, "results": []}],
    }
)


def test_attach_runs_and_reports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    monkeypatch.setenv(
        "FAKE_REGCTL_SCENARIO", "default"
    )  # inspect → sha256:abc123, empty annotations
    report = tmp_path / "scan.sarif.json"
    report.write_text(SARIF)
    result = CliRunner().invoke(
        app, ["attach", "harbor.corp/lib/redis:7.2.0", "--report", str(report)]
    )
    assert result.exit_code == 0, result.stdout
    assert "attached sarif scan" in result.stdout
    assert "sha256:ref123" in result.stdout


def test_attach_json_output_is_parseable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "default")
    report = tmp_path / "scan.sarif.json"
    report.write_text(SARIF)
    result = CliRunner().invoke(
        app,
        ["attach", "harbor.corp/lib/redis:7.2.0", "--report", str(report), "--output", "json"],
    )
    assert result.exit_code == 0, result.stdout
    last = [ln for ln in result.stdout.splitlines() if ln.strip()][-1]
    payload = json.loads(last)
    assert payload["format"] == "sarif"
    assert payload["subjectDigest"] == "sha256:abc123"


def test_attach_unrecognized_report_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "default")
    report = tmp_path / "junk.txt"
    report.write_text("not a scan report")
    result = CliRunner().invoke(
        app, ["attach", "harbor.corp/lib/redis:7.2.0", "--report", str(report)]
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, UnknownFormatError)


def test_attach_reads_report_from_stdin(
    monkeypatch: pytest.MonkeyPatch, fake_bin_path: Path
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "default")
    result = CliRunner().invoke(
        app, ["attach", "harbor.corp/lib/redis:7.2.0", "--report", "-"], input=SARIF
    )
    assert result.exit_code == 0, result.stdout
    assert "attached sarif scan" in result.stdout


def test_attach_format_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "default")
    report = tmp_path / "scan.sarif.json"
    report.write_text(SARIF)
    result = CliRunner().invoke(
        app,
        ["attach", "harbor.corp/lib/redis:7.2.0", "--report", str(report), "--format", "sarif"],
    )
    assert result.exit_code == 0, result.stdout
    assert "attached sarif scan" in result.stdout


def test_attach_signs_when_signer_configured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "default")
    monkeypatch.setenv("FAKE_COSIGN_SCENARIO", "success")
    monkeypatch.setenv("HOUBA_ATTEST_SIGNER", "keyless")
    monkeypatch.setenv("HOUBA_ATTEST_BUILDER_ID", "houba://ci")
    report = tmp_path / "scan.sarif.json"
    report.write_text(SARIF)
    result = CliRunner().invoke(
        app, ["attach", "harbor.corp/lib/redis:7.2.0", "--report", str(report)]
    )
    assert result.exit_code == 0, result.stdout
    assert "signed:" in result.stdout
    assert "https://houba.dev/predicate/scan/v1" in result.stdout


def test_attach_unsigned_when_no_signer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "default")
    monkeypatch.delenv("HOUBA_ATTEST_SIGNER", raising=False)
    report = tmp_path / "scan.sarif.json"
    report.write_text(SARIF)
    result = CliRunner().invoke(
        app, ["attach", "harbor.corp/lib/redis:7.2.0", "--report", str(report)]
    )
    assert result.exit_code == 0, result.stdout
    assert "signed:" not in result.stdout
