from __future__ import annotations

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


def _log_text(p: Path) -> str:
    return p.read_text() if p.exists() else ""


def test_keyless_no_rekor_disables_tlog_and_returns_ref(
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
    assert "--fulcio-url https://fulcio.corp" in args
    assert "--tlog-upload=false" in args  # blank rekor => no log entry
    assert "--key" not in args
    assert ref.predicate_type == "https://houba.dev/predicate/transform/v1"
    assert ref.referrer_digest.startswith("sha256:")  # parsed from cosign output


def test_kms_signer_passes_key_and_rekor(
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
    assert "--rekor-url https://rekor.corp" in args
    assert "--tlog-upload=false" not in args


def test_failure_raises_cosign_error(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_COSIGN_SCENARIO", "fail")
    with pytest.raises(CosignError):
        CosignAdapter(AttestSettings(signer="keyless")).attest(SUBJECT, STATEMENT)


def test_explicit_missing_binary_raises_cosign_error() -> None:
    with pytest.raises(CosignError, match="not found"):
        CosignAdapter(AttestSettings(signer="keyless"), binary="/nonexistent/cosign")


def test_key_signer_emits_key_flag(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The third trust model: a local key path also maps to --key (like kms).
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    cfg = AttestSettings(signer="key", key_ref="/keys/cosign.key")
    CosignAdapter(cfg).attest(SUBJECT, STATEMENT)

    args = _log_text(log)
    assert "--key /keys/cosign.key" in args
    assert "--fulcio-url" not in args


def test_keyless_blank_fulcio_omits_fulcio_flag(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Most common keyless case: no internal Fulcio configured => defer to public Sigstore,
    # so no --fulcio-url is emitted (and never a --key).
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    monkeypatch.setenv("FAKE_COSIGN_SCENARIO", "success")
    CosignAdapter(AttestSettings(signer="keyless")).attest(SUBJECT, STATEMENT)

    args = _log_text(log)
    assert "--fulcio-url" not in args
    assert "--key" not in args
