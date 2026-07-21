from __future__ import annotations

from datetime import UTC, datetime

import pytest

from knock.domain.sbom import (
    FORMAT_MEDIA_TYPES,
    SBOM_PREDICATE_TYPES,
    build_sbom_annotations,
    build_sbom_statement,
    media_type_for,
)
from knock.errors import UnknownFormatError

TS = datetime(2026, 6, 17, tzinfo=UTC)


def test_media_type_for_known_formats() -> None:
    assert media_type_for("spdx-json") == "application/spdx+json"
    assert media_type_for("cyclonedx-json") == "application/vnd.cyclonedx+json"


def test_media_type_for_unknown_raises() -> None:
    with pytest.raises(UnknownFormatError):
        media_type_for("bogus-format")


def test_format_media_types_keys_are_the_allowed_set() -> None:
    assert set(FORMAT_MEDIA_TYPES) == {"spdx-json", "cyclonedx-json"}


def test_build_sbom_annotations_emits_namespaced_facts() -> None:
    ann = build_sbom_annotations(
        prefix="io.knock",
        subject_digest="sha256:abc",
        fmt="spdx-json",
        tool="syft",
        tool_version="1.20.0",
        timestamp=TS,
    )
    assert ann["io.knock.sbom.tool"] == "syft"
    assert ann["io.knock.sbom.format"] == "spdx-json"
    assert ann["io.knock.sbom.subject"] == "sha256:abc"
    assert ann["io.knock.sbom.timestamp"] == TS.isoformat()
    assert ann["io.knock.sbom.tool.version"] == "1.20.0"


def test_build_sbom_annotations_omits_empty_version() -> None:
    ann = build_sbom_annotations(
        prefix="io.knock",
        subject_digest="sha256:abc",
        fmt="spdx-json",
        tool="syft",
        tool_version="",
        timestamp=TS,
    )
    assert "io.knock.sbom.tool.version" not in ann


def test_build_sbom_annotations_empty_prefix_emits_nothing() -> None:
    ann = build_sbom_annotations(
        prefix="",
        subject_digest="sha256:abc",
        fmt="spdx-json",
        tool="syft",
        tool_version="1.20.0",
        timestamp=TS,
    )
    assert ann == {}


def test_build_sbom_statement_spdx() -> None:
    stmt = build_sbom_statement(
        subject_name="reg.local/demo/busybox:1.36.0",
        subject_digest="sha256:abc",
        fmt="spdx-json",
        content=b'{"spdxVersion": "SPDX-2.3"}',
    )
    assert stmt["_type"] == "https://in-toto.io/Statement/v1"
    assert stmt["predicateType"] == "https://spdx.dev/Document"
    assert stmt["subject"] == [
        {"name": "reg.local/demo/busybox:1.36.0", "digest": {"sha256": "abc"}}
    ]
    assert stmt["predicate"] == {"spdxVersion": "SPDX-2.3"}


def test_build_sbom_statement_cyclonedx_predicate_type() -> None:
    stmt = build_sbom_statement(
        subject_name="x:1",
        subject_digest="sha256:def",
        fmt="cyclonedx-json",
        content=b'{"bomFormat": "CycloneDX"}',
    )
    assert stmt["predicateType"] == "https://cyclonedx.org/bom"


def test_build_sbom_statement_unknown_format_raises() -> None:
    with pytest.raises(UnknownFormatError):
        build_sbom_statement(
            subject_name="x:1", subject_digest="sha256:abc", fmt="bogus", content=b"{}"
        )


def test_sbom_predicate_types_cover_the_known_formats() -> None:
    # Every format that gets a media type must also get a predicate type.
    assert set(SBOM_PREDICATE_TYPES) == set(FORMAT_MEDIA_TYPES)
