from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from knock.adapters.command_usage import CommandUsageAdapter
from knock.domain.lifecycle import MarkIdentity
from knock.errors import UsageOracleError
from knock.ports.usage_oracle import UsageQuery


def _query() -> UsageQuery:
    return UsageQuery(
        digest="sha256:abc",
        image_ref="harbor.example/lib/redis:7.2",
        identity=MarkIdentity(policy="redis", import_="v7", variant="default"),
        since=datetime(2026, 5, 29, tzinfo=UTC),
    )


def test_seen_maps_to_last_seen_and_sends_query_json(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "oracle.log"
    monkeypatch.setenv("FAKE_ORACLE_SCENARIO", "seen")
    monkeypatch.setenv("FAKE_ORACLE_LOG", str(log))
    adapter = CommandUsageAdapter(str(fake_bin_path / "oracle"))

    obs = adapter.last_prod_usage(_query())

    assert obs.last_seen == datetime(2026, 6, 10, tzinfo=UTC)
    sent = json.loads(log.read_text().strip())
    assert sent == {
        "digest": "sha256:abc",
        "image_ref": "harbor.example/lib/redis:7.2",
        "identity": {"policy": "redis", "import": "v7", "variant": "default"},
        "since": "2026-05-29T00:00:00+00:00",
    }


def test_not_seen_maps_to_none(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ORACLE_SCENARIO", "not-seen")
    adapter = CommandUsageAdapter(str(fake_bin_path / "oracle"))
    assert adapter.last_prod_usage(_query()).last_seen is None


def test_nonzero_exit_raises(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ORACLE_SCENARIO", "fail")
    adapter = CommandUsageAdapter(str(fake_bin_path / "oracle"))
    with pytest.raises(UsageOracleError):
        adapter.last_prod_usage(_query())


def test_garbage_stdout_raises(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ORACLE_SCENARIO", "garbage")
    adapter = CommandUsageAdapter(str(fake_bin_path / "oracle"))
    with pytest.raises(UsageOracleError):
        adapter.last_prod_usage(_query())
