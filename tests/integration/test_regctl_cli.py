from datetime import datetime
from pathlib import Path

import pytest

from houba.adapters.regctl_cli import RegctlAdapter
from houba.errors import RegctlError


def test_list_tags(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "tags-redis")
    assert RegctlAdapter().list_tags("docker.io/redis") == ["7.2.0", "7.3.0", "latest"]


def test_list_tags_empty(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "empty")
    assert RegctlAdapter().list_tags("docker.io/redis") == []


def test_inspect_digest_created_annotations(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "mirror-stamped")
    info = RegctlAdapter().inspect("harbor.corp/lib/redis:7.2.0")
    assert info.digest == "sha256:abc123"
    assert info.created == datetime.fromisoformat("2026-01-02T03:04:05+00:00")
    assert info.annotations["org.opencontainers.image.base.digest"] == "sha256:src999"


def test_inspect_no_annotations(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "default")
    info = RegctlAdapter().inspect("harbor.corp/lib/redis:7.2.0")
    assert info.annotations == {}


def test_read_failure_raises_regctl_error(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "fail")
    with pytest.raises(RegctlError):
        RegctlAdapter().list_tags("docker.io/redis")


def test_garbage_json_raises_regctl_error(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "garbage")
    with pytest.raises(RegctlError, match="JSON"):
        RegctlAdapter().inspect("harbor.corp/lib/redis:7.2.0")


def test_explicit_missing_binary_raises() -> None:
    with pytest.raises(RegctlError, match="not found"):
        RegctlAdapter(binary="/nonexistent/regctl")
