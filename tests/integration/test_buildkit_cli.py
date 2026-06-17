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


def test_build_pushes_oci_mediatypes(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # OCI-native registries (e.g. Zot) reject buildkit's default Docker schema2 manifest with
    # 415; push OCI mediatypes so the manifest is accepted everywhere.
    log = tmp_path / "buildctl.log"
    monkeypatch.setenv("FAKE_BUILDCTL_LOG", str(log))
    monkeypatch.setenv("FAKE_BUILDCTL_SCENARIO", "success")
    BuildkitAdapter().build_and_push(_request(tmp_path))
    assert "oci-mediatypes=true" in log.read_text()


def test_build_and_push_failure_raises_buildkit_error(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_BUILDCTL_SCENARIO", "fail")
    with pytest.raises(BuildkitError):
        BuildkitAdapter().build_and_push(_request(tmp_path))


def test_explicit_missing_binary_raises_buildkit_error() -> None:
    with pytest.raises(BuildkitError, match="not found"):
        BuildkitAdapter(binary="/nonexistent/buildctl")


def test_build_emits_platform_opt(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "buildctl.log"
    monkeypatch.setenv("FAKE_BUILDCTL_LOG", str(log))
    df = tmp_path / "Dockerfile"
    df.write_text("FROM scratch\n")
    BuildkitAdapter().build_and_push(
        BuildRequest(
            dockerfile_path=df,
            context_dir=tmp_path,
            image_ref="reg/x:1",
            platform="linux/amd64",
        )
    )
    assert "--opt=platform=linux/amd64" in log.read_text()


def test_build_emits_provenance_opt_when_requested(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "buildctl.log"
    monkeypatch.setenv("FAKE_BUILDCTL_LOG", str(log))
    df = tmp_path / "Dockerfile"
    df.write_text("FROM scratch\n")
    BuildkitAdapter().build_and_push(
        BuildRequest(
            dockerfile_path=df,
            context_dir=tmp_path,
            image_ref="reg/x:1",
            provenance=True,
        )
    )
    assert "--opt=attest:provenance=mode=max" in log.read_text()


def test_build_omits_provenance_opt_by_default(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "buildctl.log"
    monkeypatch.setenv("FAKE_BUILDCTL_LOG", str(log))
    df = tmp_path / "Dockerfile"
    df.write_text("FROM scratch\n")
    BuildkitAdapter().build_and_push(
        BuildRequest(dockerfile_path=df, context_dir=tmp_path, image_ref="reg/x:1")
    )
    assert "attest:provenance" not in log.read_text()


def test_build_marks_registry_insecure_when_tls_disabled(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # tls_verify=False ⇒ buildkit must push over plain HTTP, else it speaks HTTPS
    # to an HTTP registry and the push fails with "server gave HTTP response to
    # HTTPS client". Mirrors regctl's `--tls disabled`.
    log = tmp_path / "buildctl.log"
    monkeypatch.setenv("FAKE_BUILDCTL_LOG", str(log))
    df = tmp_path / "Dockerfile"
    df.write_text("FROM scratch\n")
    BuildkitAdapter().build_and_push(
        BuildRequest(
            dockerfile_path=df, context_dir=tmp_path, image_ref="reg:5000/x:1", tls_verify=False
        )
    )
    assert "registry.insecure=true" in log.read_text()


def test_build_omits_registry_insecure_by_default(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "buildctl.log"
    monkeypatch.setenv("FAKE_BUILDCTL_LOG", str(log))
    df = tmp_path / "Dockerfile"
    df.write_text("FROM scratch\n")
    BuildkitAdapter().build_and_push(
        BuildRequest(dockerfile_path=df, context_dir=tmp_path, image_ref="reg/x:1")
    )
    assert "registry.insecure" not in log.read_text()
