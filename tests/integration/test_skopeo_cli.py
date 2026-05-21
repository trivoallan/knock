from pathlib import Path

import pytest

from hub2hub.adapters.skopeo_cli import SkopeoAdapter
from hub2hub.errors import SkopeoError


def test_list_tags(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_SKOPEO_SCENARIO", "list-tags-busybox")
    tags = SkopeoAdapter().list_tags("docker.io/library/busybox")
    assert tags == ["1.36", "1.37", "latest"]


def test_inspect(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_SKOPEO_SCENARIO", "inspect-busybox")
    img = SkopeoAdapter().inspect("docker.io/library/busybox:1.36")
    assert img.digest == "sha256:abc123"
    assert img.architecture == "amd64"
    assert img.os == "linux"


def test_failure_raises_skopeo_error(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_SKOPEO_SCENARIO", "fail")
    with pytest.raises(SkopeoError):
        SkopeoAdapter().inspect("docker.io/library/busybox:1.36")
