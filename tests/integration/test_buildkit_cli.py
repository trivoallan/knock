from __future__ import annotations

from pathlib import Path

import pytest

from houba.adapters.buildkit_cli import BuildkitAdapter
from houba.errors import BuildkitError
from houba.ports.image_builder import BuildRequest


def _request(tmp_path: Path) -> BuildRequest:
    df = tmp_path / "Dockerfile"
    df.write_text("FROM scratch\n")
    return BuildRequest(
        dockerfile_path=df,
        context_dir=tmp_path,
        image_ref="harbor.example.com/lib/busybox:1.36",
        build_args={"VERSION": "1.36"},
    )


def test_build_and_push_success(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "buildctl.log"
    monkeypatch.setenv("FAKE_BUILDCTL_LOG", str(log))
    monkeypatch.setenv("FAKE_BUILDCTL_SCENARIO", "success")
    BuildkitAdapter().build_and_push(_request(tmp_path))
    args = log.read_text().strip()
    assert "build" in args
    assert "harbor.example.com/lib/busybox:1.36" in args
    assert "VERSION=1.36" in args


def test_build_and_push_failure_raises_buildkit_error(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_BUILDCTL_SCENARIO", "fail")
    with pytest.raises(BuildkitError):
        BuildkitAdapter().build_and_push(_request(tmp_path))


def test_explicit_missing_binary_raises_buildkit_error() -> None:
    with pytest.raises(BuildkitError, match="not found"):
        BuildkitAdapter(binary="/nonexistent/buildctl")
