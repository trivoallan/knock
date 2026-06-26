from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import houba.cli.reconcile as cli_reconcile
from houba.cli.main import app
from houba.domain.deletion_mode import DeletionMode
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
    assert "reconcile [dry-run]" in result.stdout
    assert "status=ok" in result.stdout


def test_reconcile_json_output_is_parseable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    import json

    _env(monkeypatch)
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "empty")
    monkeypatch.setenv("HOUBA_LOG_FORMAT", "json")
    (tmp_path / "redis.yml").write_text(POLICY)
    result = CliRunner().invoke(app, ["reconcile", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0, result.stdout
    # stdout's LAST non-empty line is the RunReport JSON (journal lines may precede it).
    last = [ln for ln in result.stdout.splitlines() if ln.strip()][-1]
    payload = json.loads(last)
    assert payload["mode"] == "dry-run"
    assert payload["status"] == "ok"


BOOM_POLICY = """
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata: { name: boom }
spec:
  artifactType: image
  source: { registry: docker.io, repository: library/boom }
  imports:
    - name: v7
      tags: { includeRegex: "^7\\\\." }
      destinations: [{ project: lib, repository: boom }]
"""


def test_reconcile_partial_failure_exits_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    """Two policies, one fails during APPLY: run is partial and exits 2 (AdapterError),
    while the other policy still imports. The 'boom' policy reaches apply (its source
    `tag ls` returns a tag) but its source inspect (`image config`) blows up there."""
    _env(monkeypatch)
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "apply-fail-boom")
    (tmp_path / "redis.yml").write_text(POLICY)
    (tmp_path / "boom.yml").write_text(BOOM_POLICY)

    result = CliRunner().invoke(app, ["reconcile", str(tmp_path)])

    assert result.exit_code == 2, result.stdout
    assert "status=partial" in result.stdout
    # Good policy imported; bad policy failed — both names appear, exactly one FAILED.
    assert "✓ redis" in result.stdout
    assert "imported=1" in result.stdout
    boom_line = next(ln for ln in result.stdout.splitlines() if "boom" in ln and "FAILED" in ln)
    assert "✗ boom" in boom_line


def test_reconcile_verbose_unfolds_operations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    """--verbose unfolds per-target/per-operation detail on stdout; the recap-only
    (non-verbose) run omits it."""
    _env(monkeypatch)
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "tags-redis")
    (tmp_path / "redis.yml").write_text(POLICY)

    verbose = CliRunner().invoke(app, ["reconcile", str(tmp_path), "--verbose"])
    assert verbose.exit_code == 0, verbose.stdout
    # Destination repo line + an imported operation row are only printed with --verbose.
    assert "→ harbor.corp/lib/redis" in verbose.stdout
    assert "imported" in verbose.stdout

    quiet = CliRunner().invoke(app, ["reconcile", str(tmp_path)])
    assert quiet.exit_code == 0, quiet.stdout
    assert "→ harbor.corp/lib/redis" not in quiet.stdout


def test_reconcile_invalid_policy_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    _env(monkeypatch)
    (tmp_path / "bad.yml").write_text("not: valid: policy:")
    result = CliRunner().invoke(app, ["reconcile", str(tmp_path), "--dry-run"])
    assert result.exit_code != 0
    assert isinstance(result.exception, PolicyValidationError)


def test_reconcile_accepts_concurrency_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    _env(monkeypatch)
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "empty")
    (tmp_path / "redis.yml").write_text(POLICY)
    result = CliRunner().invoke(app, ["reconcile", str(tmp_path), "--dry-run", "-j", "4"])
    assert result.exit_code == 0, result.stdout
    assert "status=ok" in result.stdout


def test_reconcile_rejects_zero_concurrency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    _env(monkeypatch)
    (tmp_path / "redis.yml").write_text(POLICY)
    result = CliRunner().invoke(app, ["reconcile", str(tmp_path), "-j", "0"])
    assert result.exit_code != 0  # Typer rejects below the min


def test_reconcile_accepts_shard_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    _env(monkeypatch)
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "empty")
    (tmp_path / "redis.yml").write_text(POLICY)
    result = CliRunner().invoke(
        app, ["reconcile", str(tmp_path), "--dry-run", "--shard-index", "0", "--shard-count", "2"]
    )
    assert result.exit_code == 0, result.stdout


def test_reconcile_rejects_index_ge_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    _env(monkeypatch)
    (tmp_path / "redis.yml").write_text(POLICY)
    result = CliRunner().invoke(
        app, ["reconcile", str(tmp_path), "--shard-index", "2", "--shard-count", "2"]
    )
    assert result.exit_code != 0  # index must be < count


def test_reconcile_report_json_flag_emits_parseable_json_regardless_of_log_format(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    """--report-json writes a JSON RunReport to stdout even when HOUBA_LOG_FORMAT=text."""
    import json

    _env(monkeypatch)
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "empty")
    # Explicitly keep log format as text (the default) to prove --report-json overrides it.
    monkeypatch.setenv("HOUBA_LOG_FORMAT", "text")
    (tmp_path / "redis.yml").write_text(POLICY)
    result = CliRunner().invoke(app, ["reconcile", str(tmp_path), "--dry-run", "--report-json"])
    assert result.exit_code == 0, result.stdout
    # stdout must parse as JSON
    payload = json.loads(result.stdout)
    assert payload["mode"] == "dry-run"
    assert payload["status"] == "ok"


def test_cli_threads_global_deletion_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_bin_path: Path
) -> None:
    _env(monkeypatch)
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "empty")
    monkeypatch.setenv("HOUBA_DELETION_MODE", "mark")
    (tmp_path / "redis.yml").write_text(POLICY)

    captured: dict[str, object] = {}

    real = cli_reconcile.reconcile_policies

    def spy(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        captured["deletion_mode"] = kwargs.get("deletion_mode")
        return real(*args, **kwargs)

    monkeypatch.setattr(cli_reconcile, "reconcile_policies", spy)
    result = CliRunner().invoke(app, ["reconcile", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0, result.stdout
    assert captured["deletion_mode"] is DeletionMode.mark
