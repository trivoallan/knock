"""SARIF (2.1.0) scan-report mapper. Buckets findings into vuln severities."""

from __future__ import annotations

import json
from typing import Any

from houba.domain.scan.formats.base import ScanFormatMapper
from houba.domain.scan.summary import SEVERITY_VALUES as _BUCKETS
from houba.domain.scan.summary import ScanSummary
from houba.errors import ScanReportError


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rule_severities(driver: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    rules = driver.get("rules")
    if not isinstance(rules, list):
        return out
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rid = rule.get("id")
        props = rule.get("properties")
        sev = props.get("security-severity") if isinstance(props, dict) else None
        score = _to_float(sev)
        if isinstance(rid, str) and score is not None:
            out[rid] = score
    return out


def _score_to_bucket(score: float) -> str:
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


def _classify(result: dict[str, Any], severities: dict[str, float]) -> str:
    """Full fact key for one SARIF result: a `vuln.<severity>` or a `rule.<status>`."""
    props = result.get("properties")
    score = _to_float(props.get("security-severity")) if isinstance(props, dict) else None
    if score is None:
        rid = result.get("ruleId")
        if isinstance(rid, str):
            score = severities.get(rid)
    if score is not None:
        return f"vuln.{_score_to_bucket(score)}"
    # A rule/policy evaluation announces itself with an explicit SARIF `kind`. Route those to
    # rule.* so posture findings (e.g. regis EOL/hygiene via SARIF) don't inflate vuln counts.
    # Only an explicit kind triggers this; producers that omit it keep the legacy bucketing below.
    if "kind" in result:
        return "rule.passed" if result.get("kind") == "pass" else "rule.failed"
    # ponytail: no CVSS + no explicit kind -> legacy level fallback as a vuln. Ceiling: a
    # kind-less, scoreless real vuln classifies by level; fine for CVSS-emitting scanners. Upgrade
    # path: read a SARIF taxonomy/tag if a producer ever sets kind:"fail" on uncscored vulns.
    level = result.get("level")
    if level == "error":
        return "vuln.high"
    if level == "warning":
        return "vuln.medium"
    if level in ("note", "none"):
        return "vuln.low"
    return "vuln.unknown"


class SarifMapper(ScanFormatMapper):
    name = "sarif"
    report_media_type = "application/sarif+json"
    fact_keys = (*(f"vuln.{b}" for b in _BUCKETS), "rule.passed", "rule.failed")

    def recognizes(self, doc: dict[str, Any]) -> bool:
        schema = doc.get("$schema")
        if isinstance(schema, str) and "sarif" in schema.lower():
            return True
        return isinstance(doc.get("runs"), list)

    def summarize(self, report_bytes: bytes) -> ScanSummary:
        try:
            doc: Any = json.loads(report_bytes)
        except json.JSONDecodeError as e:
            raise ScanReportError(f"invalid SARIF JSON: {e}") from e
        if not isinstance(doc, dict) or not isinstance(doc.get("runs"), list):
            raise ScanReportError("SARIF report must be an object with a 'runs' array")

        counts = dict.fromkeys(self.fact_keys, 0)
        tool = ""
        tool_version = ""
        for run in doc["runs"]:
            if not isinstance(run, dict):
                continue
            tool_obj = run.get("tool")
            driver = tool_obj.get("driver") if isinstance(tool_obj, dict) else None
            driver = driver if isinstance(driver, dict) else {}
            if not tool and isinstance(driver.get("name"), str):
                tool = driver["name"]
            if not tool_version and isinstance(driver.get("version"), str):
                tool_version = driver["version"]
            severities = _rule_severities(driver)
            results = run.get("results")
            for result in results if isinstance(results, list) else []:
                if isinstance(result, dict):
                    counts[_classify(result, severities)] += 1

        facts = {k: str(counts[k]) for k in self.fact_keys}
        return ScanSummary(tool=tool, tool_version=tool_version, facts=facts)
