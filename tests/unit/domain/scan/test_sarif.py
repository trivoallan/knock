from __future__ import annotations

import json

import pytest

from houba.domain.scan.formats.sarif import SarifMapper
from houba.errors import ScanReportError


def _sarif(results: list[dict], rules: list[dict] | None = None) -> bytes:
    doc = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {"driver": {"name": "trivy", "version": "0.50.1", "rules": rules or []}},
                "results": results,
            }
        ],
    }
    return json.dumps(doc).encode()


def test_recognizes_sarif_by_schema() -> None:
    assert SarifMapper().recognizes(json.loads(_sarif([])))


def test_recognizes_sarif_by_runs_key() -> None:
    assert SarifMapper().recognizes({"version": "2.1.0", "runs": []})


def test_recognizes_rejects_non_sarif() -> None:
    assert not SarifMapper().recognizes({"bomFormat": "CycloneDX"})


def test_tool_and_version_extracted() -> None:
    s = SarifMapper().summarize(_sarif([]))
    assert s.tool == "trivy"
    assert s.tool_version == "0.50.1"


def test_security_severity_on_rule_buckets_by_cvss() -> None:
    rules = [
        {"id": "CVE-1", "properties": {"security-severity": "9.8"}},  # critical
        {"id": "CVE-2", "properties": {"security-severity": "7.5"}},  # high
        {"id": "CVE-3", "properties": {"security-severity": "5.0"}},  # medium
        {"id": "CVE-4", "properties": {"security-severity": "2.0"}},  # low
    ]
    results = [{"ruleId": f"CVE-{i}"} for i in (1, 2, 3, 4)]
    s = SarifMapper().summarize(_sarif(results, rules))
    assert s.facts["vuln.critical"] == "1"
    assert s.facts["vuln.high"] == "1"
    assert s.facts["vuln.medium"] == "1"
    assert s.facts["vuln.low"] == "1"
    assert s.facts["vuln.unknown"] == "0"


def test_level_fallback_when_no_security_severity() -> None:
    results = [{"level": "error"}, {"level": "warning"}, {"level": "note"}]
    s = SarifMapper().summarize(_sarif(results))
    assert s.facts["vuln.high"] == "1"  # error -> high
    assert s.facts["vuln.medium"] == "1"  # warning -> medium
    assert s.facts["vuln.low"] == "1"  # note -> low


def test_result_without_level_or_severity_is_unknown() -> None:
    s = SarifMapper().summarize(_sarif([{"ruleId": "X"}]))
    assert s.facts["vuln.unknown"] == "1"


def test_no_results_all_zero() -> None:
    s = SarifMapper().summarize(_sarif([]))
    assert all(
        s.facts[f"vuln.{b}"] == "0" for b in ("critical", "high", "medium", "low", "unknown")
    )


def test_kind_pass_counts_as_rule_passed() -> None:
    s = SarifMapper().summarize(_sarif([{"ruleId": "R1", "kind": "pass"}]))
    assert s.facts["rule.passed"] == "1"
    assert s.facts["rule.failed"] == "0"
    assert s.facts["vuln.high"] == "0"  # not miscounted as a vuln


def test_kind_fail_counts_as_rule_failed() -> None:
    s = SarifMapper().summarize(_sarif([{"ruleId": "R1", "kind": "fail", "level": "error"}]))
    assert s.facts["rule.failed"] == "1"
    assert s.facts["rule.passed"] == "0"
    assert s.facts["vuln.high"] == "0"  # level no longer routes to vuln once kind is explicit


def test_kind_open_counts_as_rule_failed() -> None:
    s = SarifMapper().summarize(_sarif([{"ruleId": "R1", "kind": "open"}]))
    assert s.facts["rule.failed"] == "1"


def test_cvss_score_wins_over_kind() -> None:
    s = SarifMapper().summarize(
        _sarif([{"ruleId": "R1", "kind": "pass", "properties": {"security-severity": "9.8"}}])
    )
    assert s.facts["vuln.critical"] == "1"
    assert s.facts["rule.passed"] == "0"


def test_rule_keys_present_and_zero_when_no_results() -> None:
    s = SarifMapper().summarize(_sarif([]))
    assert s.facts["rule.passed"] == "0"
    assert s.facts["rule.failed"] == "0"


def test_malformed_json_raises_scan_report_error() -> None:
    with pytest.raises(ScanReportError, match="JSON"):
        SarifMapper().summarize(b"{not json")


def test_missing_runs_raises_scan_report_error() -> None:
    with pytest.raises(ScanReportError, match="runs"):
        SarifMapper().summarize(b'{"version": "2.1.0"}')
