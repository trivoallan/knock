from __future__ import annotations

import json
from pathlib import Path

import pytest

from houba.adapters.cosign_cli import CosignAdapter
from houba.config import AttestSettings
from houba.errors import CosignError

STATEMENT = {
    "_type": "https://in-toto.io/Statement/v1",
    "subject": [{"name": "reg/x:1", "digest": {"sha256": "out"}}],
    "predicateType": "https://houba.dev/predicate/transform/v1",
    "predicate": {"policy": "p", "import": "i"},
}
SUBJECT = "reg.local/hardened/redis@sha256:out123"

# v2 flags cosign v3 rejects ("cannot specify service URLs and use signing config").
FORBIDDEN = ("--fulcio-url", "--rekor-url", "--tlog-upload")


def _log_text(p: Path) -> str:
    return p.read_text() if p.exists() else ""


def test_attest_uses_signing_config_not_service_flags(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    monkeypatch.setenv("FAKE_COSIGN_SCENARIO", "success")
    cfg = AttestSettings(signer="keyless", fulcio_url="https://fulcio.corp")
    ref = CosignAdapter(cfg).attest(SUBJECT, STATEMENT)

    args = _log_text(log)
    assert "attest" in args
    assert SUBJECT in args
    assert "--type https://houba.dev/predicate/transform/v1" in args
    assert "--predicate" in args
    assert "--signing-config" in args
    assert "--key" not in args  # keyless
    for flag in FORBIDDEN:
        assert flag not in args
    assert ref.predicate_type == "https://houba.dev/predicate/transform/v1"
    assert ref.referrer_digest.startswith("sha256:")


def test_kms_signer_passes_key_and_signing_config(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    cfg = AttestSettings(
        signer="kms", key_ref="awskms://alias/houba", rekor_url="https://rekor.corp"
    )
    CosignAdapter(cfg).attest(SUBJECT, STATEMENT)

    args = _log_text(log)
    assert "--key awskms://alias/houba" in args
    assert "--signing-config" in args
    for flag in FORBIDDEN:
        assert flag not in args


def test_key_signer_emits_key_flag(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    cfg = AttestSettings(signer="key", key_ref="/keys/cosign.key")
    CosignAdapter(cfg).attest(SUBJECT, STATEMENT)

    args = _log_text(log)
    assert "--key /keys/cosign.key" in args
    assert "--signing-config" in args
    for flag in FORBIDDEN:
        assert flag not in args


def test_keyless_blank_fulcio_omits_key_and_service_flags(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    monkeypatch.setenv("FAKE_COSIGN_SCENARIO", "success")
    CosignAdapter(AttestSettings(signer="keyless")).attest(SUBJECT, STATEMENT)

    args = _log_text(log)
    assert "--key" not in args
    assert "--signing-config" in args
    for flag in FORBIDDEN:
        assert flag not in args


def test_failure_raises_cosign_error(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_COSIGN_SCENARIO", "fail")
    with pytest.raises(CosignError):
        CosignAdapter(AttestSettings(signer="keyless")).attest(SUBJECT, STATEMENT)


def test_explicit_missing_binary_raises_cosign_error() -> None:
    with pytest.raises(CosignError, match="not found"):
        CosignAdapter(AttestSettings(signer="keyless"), binary="/nonexistent/cosign")


def test_signing_config_file_content_carries_operator_and_media_type(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Capture the actual signing-config file the adapter writes (deleted post-run otherwise),
    # and verify its content — operator flows from builder_id, media type is v0.2.
    captured = tmp_path / "captured-signing-config.json"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(tmp_path / "cosign.log"))
    monkeypatch.setenv("FAKE_COSIGN_SIGNING_CONFIG", str(captured))
    monkeypatch.setenv("FAKE_COSIGN_SCENARIO", "success")
    cfg = AttestSettings(
        signer="kms",
        key_ref="awskms://alias/houba",
        rekor_url="https://rekor.corp",
        builder_id="https://houba.example/builders/main",
    )
    CosignAdapter(cfg).attest(SUBJECT, STATEMENT)

    written = json.loads(captured.read_text())
    assert written["mediaType"] == "application/vnd.dev.sigstore.signingconfig.v0.2+json"
    assert written["rekorTlogUrls"][0]["url"] == "https://rekor.corp"
    assert written["rekorTlogUrls"][0]["operator"] == "https://houba.example/builders/main"
    assert written["rekorTlogConfig"] == {"selector": "ANY"}
