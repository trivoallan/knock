from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from houba.cli.main import app
from houba.errors import PolicyValidationError

POLICY = """
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata: { name: redis }
spec:
  artifactType: image
  source: { registry: docker.io, repository: library/redis }
  imports:
    - name: v7
      tags: { includeRegex: "^7\\\\." }
      destinations: [{ project: lib, repository: redis }]
"""


def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOUBA_HARBOR_URL", "https://h")
    monkeypatch.setenv("HOUBA_HARBOR_USER", "u")
    monkeypatch.setenv("HOUBA_HARBOR_PASSWORD", "p")
    monkeypatch.setenv("HOUBA_GITLAB_URL", "https://g")
    monkeypatch.setenv("HOUBA_GITLAB_TOKEN", "t")
    monkeypatch.setenv("HOUBA_GITLAB_GROUP", "g")
    monkeypatch.setenv(
        "HOUBA_REGISTRIES", '{"only": {"host": "harbor.corp", "username": "r", "password": "x"}}'
    )


def test_reconcile_runs_and_reports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    _env(monkeypatch)
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "empty")  # no source tags → nothing to copy
    (tmp_path / "redis.yml").write_text(POLICY)
    result = CliRunner().invoke(app, ["reconcile", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0, result.stdout
    assert "reconcile" in result.stdout


def test_reconcile_invalid_policy_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    _env(monkeypatch)
    (tmp_path / "bad.yml").write_text("not: valid: policy:")
    result = CliRunner().invoke(app, ["reconcile", str(tmp_path), "--dry-run"])
    assert result.exit_code != 0
    assert isinstance(result.exception, PolicyValidationError)
