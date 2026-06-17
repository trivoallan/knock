from __future__ import annotations

from datetime import UTC, datetime

import pytest

from houba.domain.sbom import (
    FORMAT_MEDIA_TYPES,
    build_sbom_annotations,
    media_type_for,
)
from houba.errors import UnknownFormatError

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
        prefix="io.houba",
        subject_digest="sha256:abc",
        fmt="spdx-json",
        tool="syft",
        tool_version="1.20.0",
        timestamp=TS,
    )
    assert ann["io.houba.sbom.tool"] == "syft"
    assert ann["io.houba.sbom.format"] == "spdx-json"
    assert ann["io.houba.sbom.subject"] == "sha256:abc"
    assert ann["io.houba.sbom.timestamp"] == TS.isoformat()
    assert ann["io.houba.sbom.tool.version"] == "1.20.0"


def test_build_sbom_annotations_omits_empty_version() -> None:
    ann = build_sbom_annotations(
        prefix="io.houba",
        subject_digest="sha256:abc",
        fmt="spdx-json",
        tool="syft",
        tool_version="",
        timestamp=TS,
    )
    assert "io.houba.sbom.tool.version" not in ann


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
