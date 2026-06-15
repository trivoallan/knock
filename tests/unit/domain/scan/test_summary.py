from __future__ import annotations

from datetime import UTC, datetime

from houba.domain.scan.summary import Severity, ScanSummary, build_scan_annotations, gate_breached

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


def _facts(**counts: int) -> dict[str, str]:
    base = {f"vuln.{s.value}": "0" for s in Severity}
    base.update({f"vuln.{k}": str(v) for k, v in counts.items()})
    return base


def test_gate_breached_at_or_above_threshold() -> None:
    assert gate_breached(_facts(critical=1), Severity.high) is True
    assert gate_breached(_facts(high=2), Severity.high) is True
    assert gate_breached(_facts(medium=5), Severity.high) is False


def test_gate_unknown_is_lowest_and_targetable() -> None:
    assert gate_breached(_facts(unknown=1), Severity.low) is True
    assert gate_breached(_facts(unknown=1), Severity.unknown) is True
    assert gate_breached(_facts(low=1), Severity.unknown) is True  # unknown gates on any finding
    # but unknown is NOT folded in at medium+ (the caller accepts uncertain findings there)
    assert gate_breached(_facts(unknown=1), Severity.medium) is False
    assert gate_breached(_facts(unknown=1), Severity.critical) is False


def test_gate_no_findings_or_missing_facts() -> None:
    assert gate_breached(_facts(), Severity.unknown) is False
    assert gate_breached({}, Severity.critical) is False
    assert gate_breached({"vuln.critical": "notanint"}, Severity.critical) is False
