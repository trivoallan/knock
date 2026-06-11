from typing import Any

import pytest

from houba.domain.mirror_policy import TransformStep
from houba.domain.transform import render_dockerfile, validate_transform_steps
from houba.errors import PolicyValidationError


def _step(name: str, params: dict[str, Any]) -> TransformStep:
    return TransformStep(name=name, params=params)


def test_accepts_the_two_known_steps() -> None:
    validate_transform_steps(
        [
            _step("injectCA", {"certs": ["corp-root", "partner-ca"]}),
            _step("rewritePackageSources", {"mirror": "corp"}),
        ]
    )  # no raise


def test_empty_is_valid() -> None:
    validate_transform_steps([])  # no raise


def test_rejects_unknown_step_name() -> None:
    with pytest.raises(PolicyValidationError, match="unknown transform step 'setTimezone'"):
        validate_transform_steps([_step("setTimezone", {"tz": "UTC"})])


def test_rejects_injectca_without_list_of_strings() -> None:
    with pytest.raises(PolicyValidationError, match=r"injectCA\.certs"):
        validate_transform_steps([_step("injectCA", {"certs": "corp-root"})])


def test_rejects_injectca_empty_list() -> None:
    with pytest.raises(PolicyValidationError, match=r"injectCA\.certs"):
        validate_transform_steps([_step("injectCA", {"certs": []})])


def test_rejects_rewrite_without_string_mirror() -> None:
    with pytest.raises(PolicyValidationError, match=r"rewritePackageSources\.mirror"):
        validate_transform_steps([_step("rewritePackageSources", {"mirror": ["corp"]})])


# ---------------------------------------------------------------------------
# render_dockerfile
# ---------------------------------------------------------------------------


def test_render_inject_ca_only() -> None:
    df = render_dockerfile(
        "docker.io/library/redis@sha256:abc",
        ca_cert_filenames=["corp-root.crt", "partner.crt"],
        apt_mirror=None,
        apk_mirror=None,
    )
    assert df.startswith("FROM docker.io/library/redis@sha256:abc\n")
    assert "COPY corp-root.crt partner.crt /usr/local/share/ca-certificates/" in df
    assert "RUN update-ca-certificates" in df
    assert "sed" not in df


def test_render_rewrite_apt_and_apk() -> None:
    df = render_dockerfile(
        "alpine@sha256:def",
        ca_cert_filenames=[],
        apt_mirror="https://mirror.corp",
        apk_mirror="https://mirror.corp",
    )
    assert "update-ca-certificates" not in df
    assert "/etc/apt/sources.list" in df
    assert "/etc/apk/repositories" in df
    assert "s#https?://[^/]+#https://mirror.corp#g" in df


def test_render_apt_only_omits_apk() -> None:
    df = render_dockerfile(
        "x@sha256:1", ca_cert_filenames=[], apt_mirror="https://m", apk_mirror=None
    )
    assert "/etc/apt/sources.list" in df
    assert "/etc/apk/repositories" not in df


def test_render_both_steps_ca_before_rewrite() -> None:
    df = render_dockerfile(
        "x@sha256:1",
        ca_cert_filenames=["c.crt"],
        apt_mirror="https://m",
        apk_mirror=None,
    )
    assert df.index("update-ca-certificates") < df.index("/etc/apt/sources.list")
