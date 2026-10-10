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


def test_sign_signs_the_image_with_key_and_signing_config(fake_bin_path, tmp_path, monkeypatch):
    log = tmp_path / "cosign.log"
    scfg = tmp_path / "scfg.json"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    monkeypatch.setenv("FAKE_COSIGN_SIGNING_CONFIG", str(scfg))
    _adapter().sign(SUBJECT)
    argv = log.read_text().split()
    assert argv[0] == "sign"
    assert "--yes" in argv
    assert argv[argv.index("--key") + 1] == "/tmp/cosign.pub"
    assert argv[-1] == SUBJECT
    assert "--type" not in argv  # an image signature, not a predicate
    assert scfg.exists()  # same signing-config as attest


def test_sign_failure_raises(fake_bin_path, monkeypatch):
    import pytest

    from knock.errors import CosignError

    monkeypatch.setenv("FAKE_COSIGN_SCENARIO", "fail")
    with pytest.raises(CosignError, match="cosign sign failed"):
        _adapter().sign(SUBJECT)


def test_verify_signature_true_on_image_signature_claim(fake_bin_path, tmp_path, monkeypatch):
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    monkeypatch.setenv("FAKE_COSIGN_SIGVERIFY_SCENARIO", "signed")
    assert _adapter().verify_signature(SUBJECT) is True
    argv = log.read_text().split()
    assert argv[0] == "verify"
    assert "--insecure-ignore-tlog=true" in argv


def test_verify_signature_rejects_attestation_only_claim(fake_bin_path, monkeypatch):
    # cosign v3 `verify` exits 0 on an attestation-only image: the claim type decides.
    monkeypatch.setenv("FAKE_COSIGN_SIGVERIFY_SCENARIO", "attested-only")
    assert _adapter().verify_signature(SUBJECT) is False


def test_verify_signature_false_when_none_or_garbage(fake_bin_path, monkeypatch):
    for scenario in ("none", "garbage"):
        monkeypatch.setenv("FAKE_COSIGN_SIGVERIFY_SCENARIO", scenario)
        assert _adapter().verify_signature(SUBJECT) is False


def test_sign_and_verify_signature_allow_http_on_plain_http_registry(
    fake_bin_path, tmp_path, monkeypatch
):
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    subject = "registry.local:5000/app@sha256:" + "c" * 64
    adapter = _roster_adapter()
    adapter.sign(subject)
    adapter.verify_signature(subject)
    sign_line, verify_line = log.read_text().splitlines()
    assert INSECURE in sign_line
    assert INSECURE in verify_line


# --- verification with a file key (design decision 9 of stage-and-promote-rebuilds) ---

_KIND = "ENCRYPTED SIGSTORE PRIVATE KEY"
PRIVATE = f"-----BEGIN {_KIND}-----\nZmFrZQ==\n-----END {_KIND}-----\n"
PUBLIC = "-----BEGIN PUBLIC KEY-----\nZmFrZQ==\n-----END PUBLIC KEY-----\n"


def _key_after(line: str) -> str:
    argv = line.split()
    return argv[argv.index("--key") + 1]


def test_verify_with_a_private_key_file_derives_the_public_key(
    fake_bin_path, tmp_path, monkeypatch
):
    key = tmp_path / "cosign.key"
    key.write_text(PRIVATE)
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    adapter = CosignAdapter(AttestSettings(signer="key", key_ref=str(key)))
    assert adapter.verify(SUBJECT, "https://knock.dev/predicate/scan/v1") != []
    derive, verify = log.read_text().splitlines()
    # cosign refuses a private key for verification: derive its public half first.
    assert derive.split()[0] == "public-key" and _key_after(derive) == str(key)
    assert verify.split()[0] == "verify-attestation" and _key_after(verify) != str(key)


def test_verify_signature_with_a_private_key_file_derives_the_public_key(
    fake_bin_path, tmp_path, monkeypatch
):
    key = tmp_path / "cosign.key"
    key.write_text(PRIVATE)
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    adapter = CosignAdapter(AttestSettings(signer="key", key_ref=str(key)))
    assert adapter.verify_signature(SUBJECT) is True
    derive, verify = log.read_text().splitlines()
    assert derive.split()[0] == "public-key"
    assert verify.split()[0] == "verify" and _key_after(verify) != str(key)


def test_verify_with_a_public_key_file_uses_it_as_is(fake_bin_path, tmp_path, monkeypatch):
    key = tmp_path / "cosign.pub"
    key.write_text(PUBLIC)
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    CosignAdapter(AttestSettings(signer="key", key_ref=str(key))).verify(SUBJECT, "https://k/p")
    (verify,) = log.read_text().splitlines()
    assert _key_after(verify) == str(key)


def test_verify_with_an_unusable_private_key_is_an_error(fake_bin_path, tmp_path, monkeypatch):
    import pytest

    from knock.errors import CosignError

    key = tmp_path / "cosign.key"
    key.write_text(PRIVATE)
    monkeypatch.setenv("FAKE_COSIGN_PUBKEY_SCENARIO", "fail")
    adapter = CosignAdapter(AttestSettings(signer="key", key_ref=str(key)))
    # A broken key is a fault, not "no attestation found".
    with pytest.raises(CosignError, match="public key"):
        adapter.verify(SUBJECT, "https://k/p")


def test_verify_with_kms_passes_the_reference_unchanged(fake_bin_path, tmp_path, monkeypatch):
    log = tmp_path / "cosign.log"
    monkeypatch.setenv("FAKE_COSIGN_LOG", str(log))
    ref = "awskms:///alias/knock"
    CosignAdapter(AttestSettings(signer="kms", key_ref=ref)).verify(SUBJECT, "https://k/p")
    (verify,) = log.read_text().splitlines()
    assert _key_after(verify) == ref


def test_has_attestation_is_true_when_cosign_verifies_an_attestation(fake_bin_path, monkeypatch):
    monkeypatch.setenv("FAKE_COSIGN_VERIFY_SCENARIO", "verified")
    assert _adapter().has_attestation(SUBJECT, "https://knock.dev/predicate/transform/v1") is True


def test_has_attestation_is_false_when_nothing_verifies(fake_bin_path, monkeypatch):
    for scenario in ("none", "verifyfail"):
        monkeypatch.setenv("FAKE_COSIGN_VERIFY_SCENARIO", scenario)
        assert (
            _adapter().has_attestation(SUBJECT, "https://knock.dev/predicate/transform/v1") is False
        )


def test_has_attestation_does_not_read_the_predicate(fake_bin_path, monkeypatch):
    # A transform predicate has no `summary`: `verify` drops it, `has_attestation` must not.
    monkeypatch.setenv("FAKE_COSIGN_PRED", '{"transformed": true}')
    adapter = _adapter()
    assert adapter.verify(SUBJECT, "https://knock.dev/predicate/transform/v1") == []
    assert adapter.has_attestation(SUBJECT, "https://knock.dev/predicate/transform/v1") is True
