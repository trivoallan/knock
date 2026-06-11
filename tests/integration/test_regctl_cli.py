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


def test_list_tags_repo_not_found_returns_empty(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A never-pushed destination repo → regctl exits non-zero with NAME_UNKNOWN.
    # That means "no tags", not a hard error — else the very first reconcile (empty
    # mirror) would always fail. Surfaced by real-registry testing.
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "notfound")
    assert RegctlAdapter().list_tags("localhost:5001/demo/absent") == []


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


def _log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log = tmp_path / "regctl.log"
    monkeypatch.setenv("FAKE_REGCTL_LOG", str(log))
    return log


def test_copy_invokes_image_copy(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(tmp_path, monkeypatch)
    RegctlAdapter().copy("docker.io/redis:7.2.0", "harbor.corp/lib/redis:7.2.0")
    assert "image copy docker.io/redis:7.2.0 harbor.corp/lib/redis:7.2.0" in log.read_text()


def test_annotate_emits_one_flag_per_annotation(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(tmp_path, monkeypatch)
    RegctlAdapter().annotate(
        "harbor.corp/lib/redis:7.2.0",
        {"org.opencontainers.image.base.digest": "sha256:src", "io.houba.lineage": "copy"},
    )
    line = log.read_text()
    assert "image mod" in line
    assert "--annotation org.opencontainers.image.base.digest=sha256:src" in line
    assert "--annotation io.houba.lineage=copy" in line


def test_delete_tag_invokes_tag_rm(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(tmp_path, monkeypatch)
    RegctlAdapter().delete_tag("harbor.corp/lib/redis:6.0.0")
    assert "tag rm harbor.corp/lib/redis:6.0.0" in log.read_text()


def test_write_failure_raises_regctl_error(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "fail")
    with pytest.raises(RegctlError):
        RegctlAdapter().copy("a:1", "b:1")


# Fix 1 — created edge cases (→ None contract for Phase 7's pushed_at)


def test_inspect_invalid_created_is_none(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "created-invalid")
    assert RegctlAdapter().inspect("x:1").created is None


def test_inspect_absent_created_is_none(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "no-created")
    assert RegctlAdapter().inspect("x:1").created is None


# Fix 2 — shutil.which → None branch


def test_no_binary_in_path_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Résolution lazy : la construction réussit dans un env sans regctl ; l'erreur
    # ne survient qu'au premier appel (pour ne pas bloquer build_container).
    monkeypatch.setenv("PATH", "")
    adapter = RegctlAdapter()
    with pytest.raises(RegctlError, match="not found in PATH"):
        adapter.list_tags("docker.io/redis")


# Fix 3 — _json non-dict branch


def test_inspect_non_object_json_raises(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_REGCTL_SCENARIO", "manifest-array")
    with pytest.raises(RegctlError, match="expected JSON object"):
        RegctlAdapter().inspect("x:1")


# Fix 4 — annotation value containing '='


def test_annotate_value_with_equals_is_passed_through(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(tmp_path, monkeypatch)
    RegctlAdapter().annotate("r:1", {"k": "a=b=c"})
    assert "--annotation k=a=b=c" in log.read_text()


def test_login_invokes_registry_login_with_password_on_stdin(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(tmp_path, monkeypatch)
    RegctlAdapter().login("harbor.corp", username="robot", password="s3cret", tls_verify=True)
    line = log.read_text()
    assert "registry login --user robot --pass-stdin harbor.corp" in line
    assert "s3cret" not in line  # password is on stdin, never in argv


def test_login_tls_disabled(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(tmp_path, monkeypatch)
    RegctlAdapter().login("localhost:5000", username="u", password="p", tls_verify=False)
    assert "--tls disabled" in log.read_text()
