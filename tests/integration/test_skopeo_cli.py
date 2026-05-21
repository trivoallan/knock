from pathlib import Path

import pytest

from houba.adapters.skopeo_cli import SkopeoAdapter
from houba.errors import SkopeoError


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


def test_garbage_output_raises_skopeo_error(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """skopeo retourne du non-JSON → SkopeoError plutôt que JSONDecodeError."""
    monkeypatch.setenv("FAKE_SKOPEO_SCENARIO", "garbage")
    with pytest.raises(SkopeoError, match="invalid JSON"):
        SkopeoAdapter().inspect("docker.io/library/busybox:1.36")


def test_missing_digest_raises_skopeo_error(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """skopeo retourne du JSON sans le champ Digest → SkopeoError, pas KeyError."""
    monkeypatch.setenv("FAKE_SKOPEO_SCENARIO", "missing-digest")
    with pytest.raises(SkopeoError, match="Digest"):
        SkopeoAdapter().inspect("docker.io/library/busybox:1.36")


def test_explicit_missing_binary_raises_skopeo_error() -> None:
    """Si le constructeur reçoit un chemin explicite qui n'existe pas, échec immédiat."""
    with pytest.raises(SkopeoError, match="not found"):
        SkopeoAdapter(binary="/nonexistent/path/to/skopeo")
