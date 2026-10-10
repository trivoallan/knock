from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knock.cli.main import app
from knock.errors import ConfigError

POLICY = """
apiVersion: knock.io/v1alpha1
kind: MirrorPolicy
metadata: { name: redis }
spec:
  artifactType: image
  source: { registry: docker.io, repository: library/redis }
  imports:
    - name: v7
      tags: { includeRegex: "^7\\\\." }
      transform: [ { setTimezone: { zone: UTC } } ]
      destinations: [{ registry: only, project: lib, repository: redis }]
"""
ROSTER = '{"only": {"host": "harbor.corp"}, "stage": {"host": "stage.local"}}'
EMPTY = {"apiVersion": "knock.io/v1alpha1", "kind": "StagedRebuilds", "entries": []}


def _setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, doc: object) -> tuple[Path, Path]:
    monkeypatch.setenv("KNOCK_REGISTRIES", ROSTER)
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "redis.yml").write_text(POLICY)
    staged = tmp_path / "staged.json"
    staged.write_text(json.dumps(doc))
    return policies, staged


def test_promote_an_empty_file_places_nothing_and_exits_0(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    policies, staged = _setup(monkeypatch, tmp_path, EMPTY)
    log = tmp_path / "regctl.log"
    monkeypatch.setenv("FAKE_REGCTL_LOG", str(log))
    result = CliRunner().invoke(app, ["promote", str(policies), "--staged", str(staged)])
    assert result.exit_code == 0, result.stdout
    assert "promote [apply] status=ok" in result.stdout
    assert not log.exists()


@pytest.mark.parametrize(
    "doc",
    [
        {**EMPTY, "kind": "ReconcilePlan"},
        {**EMPTY, "entries": [{"policy": "redis", "verdict": "pass"}]},
        "not a document",
    ],
)
def test_promote_refuses_an_invalid_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path, doc: object
) -> None:
    policies, staged = _setup(monkeypatch, tmp_path, doc)
    result = CliRunner().invoke(app, ["promote", str(policies), "--staged", str(staged)])
    assert isinstance(result.exception, ConfigError)  # exit 3 through knock.cli.main


def test_promote_refuses_a_missing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    policies, _ = _setup(monkeypatch, tmp_path, EMPTY)
    result = CliRunner().invoke(app, ["promote", str(policies), "--staged", str(tmp_path / "no")])
    assert isinstance(result.exception, ConfigError)


def test_promote_fails_an_entry_it_cannot_trust_and_exits_non_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    entry = {
        "policy": "redis",
        "import": "v7",
        "variant": "default",
        "kind": "import",
        "destination": "harbor.corp/lib/redis",
        "tag": "7.2.0",
        "source": "docker.io/library/redis",
        "sourceTag": "7.2.0",
        "sourceDigest": "sha256:a",
        # not the destination re-rooted under a roster registry
        "staged": "evil.example/lib/redis",
        "stagedDigest": "sha256:b",
        "aliases": [],
    }
    policies, staged = _setup(monkeypatch, tmp_path, {**EMPTY, "entries": [entry]})
    log = tmp_path / "regctl.log"
    monkeypatch.setenv("FAKE_REGCTL_LOG", str(log))
    result = CliRunner().invoke(app, ["promote", str(policies), "--staged", str(staged)])
    assert result.exit_code == 1, result.stdout
    assert "promote [apply] status=failed" in result.stdout
    assert not log.exists() or "image copy" not in log.read_text()
