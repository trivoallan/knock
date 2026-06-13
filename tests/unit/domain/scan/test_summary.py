from __future__ import annotations

from datetime import UTC, datetime

from houba.domain.scan.summary import ScanSummary, build_scan_annotations

TS = datetime(2026, 6, 12, 9, 30, tzinfo=UTC)


def _summary() -> ScanSummary:
    return ScanSummary(
        tool="trivy",
        tool_version="0.50.1",
        facts={"vuln.critical": "3", "vuln.high": "12"},
    )


def test_common_envelope_keys_present() -> None:
    a = build_scan_annotations(
        _summary(), prefix="io.houba", subject_digest="sha256:abc", fmt="sarif", timestamp=TS
    )
    assert a["io.houba.scan.tool"] == "trivy"
    assert a["io.houba.scan.tool.version"] == "0.50.1"
    assert a["io.houba.scan.format"] == "sarif"
    assert a["io.houba.scan.timestamp"] == "2026-06-12T09:30:00+00:00"
    assert a["io.houba.scan.subject"] == "sha256:abc"


def test_facts_are_namespaced_under_scan() -> None:
    a = build_scan_annotations(
        _summary(), prefix="io.houba", subject_digest="sha256:abc", fmt="sarif", timestamp=TS
    )
    assert a["io.houba.scan.vuln.critical"] == "3"
    assert a["io.houba.scan.vuln.high"] == "12"


def test_empty_prefix_yields_no_annotations() -> None:
    a = build_scan_annotations(
        _summary(), prefix="", subject_digest="sha256:abc", fmt="sarif", timestamp=TS
    )
    assert a == {}


def test_empty_tool_version_omits_the_key() -> None:
    s = ScanSummary(tool="grype", tool_version="", facts={})
    a = build_scan_annotations(
        s, prefix="io.houba", subject_digest="sha256:abc", fmt="sarif", timestamp=TS
    )
    assert "io.houba.scan.tool.version" not in a
    assert a["io.houba.scan.tool"] == "grype"
