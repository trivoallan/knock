from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from houba.adapters.syft_cli import SyftAdapter
from houba.errors import SyftError

DIGEST_REF = "reg.example.com/x@sha256:" + "a" * 64


def test_generate_emits_one_output_per_format(
    fake_bin_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "syft.log"
    monkeypatch.setenv("FAKE_SYFT_LOG", str(log))

    docs = SyftAdapter().generate(DIGEST_REF, ["spdx-json", "cyclonedx-json"])

    assert {d.format for d in docs} == {"spdx-json", "cyclonedx-json"}
    assert {d.media_type for d in docs} == {
        "application/spdx+json",
        "application/vnd.cyclonedx+json",
    }
    assert all(d.content for d in docs)  # read back the fake-bin's stub bytes
    text = log.read_text()
    assert "-o spdx-json=" in text
    assert "-o cyclonedx-json=" in text
    assert f"registry:{DIGEST_REF}" in text


def test_generate_writes_auth_and_insecure_into_config(
    fake_bin_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = tmp_path / "captured-config.yaml"
    monkeypatch.setenv("FAKE_SYFT_CONFIG", str(captured))

    SyftAdapter().generate(
        DIGEST_REF, ["spdx-json"], tls_verify=False, username="robot", password="secret"
    )

    cfg = yaml.safe_load(captured.read_text())  # proves JSON-as-YAML parses
    reg = cfg["registry"]
    assert reg["insecure-use-http"] is True
    assert reg["insecure-skip-tls-verify"] is True
    assert reg["auth"][0]["authority"] == "reg.example.com"
    assert reg["auth"][0]["username"] == "robot"
    assert reg["auth"][0]["password"] == "secret"


def test_generate_no_auth_when_creds_absent(
    fake_bin_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = tmp_path / "captured-config.yaml"
    monkeypatch.setenv("FAKE_SYFT_CONFIG", str(captured))

    SyftAdapter().generate(DIGEST_REF, ["spdx-json"])  # tls_verify=True, no creds

    cfg = yaml.safe_load(captured.read_text())
    assert "auth" not in cfg["registry"]
    assert "insecure-use-http" not in cfg["registry"]


def test_generate_raises_syfterror_on_failure(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_SYFT_SCENARIO", "fail")
    with pytest.raises(SyftError):
        SyftAdapter().generate(DIGEST_REF, ["spdx-json"])


def test_generate_rejects_unknown_format(fake_bin_path: Path) -> None:
    from houba.errors import UnknownFormatError

    with pytest.raises(UnknownFormatError):
        SyftAdapter().generate(DIGEST_REF, ["bogus"])


def test_missing_binary_raises() -> None:
    with pytest.raises(SyftError):
        SyftAdapter(binary="/nonexistent/syft")
