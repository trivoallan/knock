from __future__ import annotations

from knock.adapters.cosign_cli import CosignAdapter
from knock.config import AttestSettings
from knock.ports.attestor import VerifiedPredicate

SUBJECT = "reg.example/app@sha256:" + "c" * 64


def _adapter():
    return CosignAdapter(AttestSettings(signer="key", key_ref="/tmp/cosign.pub"))


def test_verify_returns_predicate(fake_bin_path, monkeypatch):
    monkeypatch.setenv("FAKE_COSIGN_VERIFY_SCENARIO", "verified")
    out = _adapter().verify(SUBJECT, "https://knock.dev/predicate/scan/v1")
    assert out == [
        VerifiedPredicate(summary={"vuln.critical": "0"}, attested_at="2026-06-24T00:00:00+00:00")
    ]


def test_verify_none_is_empty_list(fake_bin_path, monkeypatch):
    monkeypatch.setenv("FAKE_COSIGN_VERIFY_SCENARIO", "none")
    assert _adapter().verify(SUBJECT, "https://knock.dev/predicate/scan/v1") == []


def test_verify_verification_failure_is_empty_list(fake_bin_path, monkeypatch):
    monkeypatch.setenv("FAKE_COSIGN_VERIFY_SCENARIO", "verifyfail")
    assert _adapter().verify(SUBJECT, "https://knock.dev/predicate/scan/v1") == []


def test_verify_passes_key_and_tlog_flags(fake_bin_path, tmp_path, monkeypatch):
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    monkeypatch.setenv("FAKE_COSIGN_VERIFY_SCENARIO", "verified")
    _adapter().verify(SUBJECT, "https://knock.dev/predicate/scan/v1")
    argv = log.read_text()
    assert "verify-attestation" in argv
    assert "--key" in argv
    assert "--insecure-ignore-tlog=true" in argv


INSECURE = "--allow-insecure-registry --allow-http-registry"


def _roster_adapter():
    from knock.config import RegistryConfig

    return CosignAdapter(
        AttestSettings(signer="key", key_ref="/tmp/cosign.pub"),
        roster={
            "local": RegistryConfig(host="registry.local:5000", tls_verify=False),
            "corp": RegistryConfig(host="reg.example"),
        },
    )


def test_attest_and_verify_allow_http_when_roster_says_tls_verify_false(
    fake_bin_path, tmp_path, monkeypatch
):
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    subject = "registry.local:5000/app@sha256:" + "c" * 64
    adapter = _roster_adapter()
    adapter.attest(subject, {"predicateType": "https://knock.dev/p", "predicate": {}})
    adapter.verify(subject, "https://knock.dev/p")
    attest_line, verify_line = log.read_text().splitlines()
    assert INSECURE in attest_line
    assert INSECURE in verify_line


def test_tls_or_unknown_registry_gets_no_insecure_flags(fake_bin_path, tmp_path, monkeypatch):
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    adapter = _roster_adapter()
    for subject in (SUBJECT, "other.example/app@sha256:" + "c" * 64):
        adapter.attest(subject, {"predicateType": "https://knock.dev/p", "predicate": {}})
        adapter.verify(subject, "https://knock.dev/p")
    assert "--allow-" not in log.read_text()
