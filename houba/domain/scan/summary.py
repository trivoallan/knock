"""Build the scan-result stamp annotations for an attached referrer (sibling of stamp.py).

OCI-standard facts are not re-emitted here (the image already carries them); this module
emits only the `{prefix}.scan.*` summary that makes a scan referrer queryable. The full
native report travels as the referrer blob, untouched. No I/O, no config.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime


class Severity(enum.StrEnum):
    """Vuln severity, declared highest → lowest (definition order IS the rank)."""

    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    unknown = "unknown"


SEVERITY_VALUES: tuple[str, ...] = tuple(s.value for s in Severity)  # rank order, highest first


def _count(raw: str | None) -> int:
    try:
        return int(raw) if raw is not None else 0
    except ValueError:
        return 0


def gate_breached(facts: dict[str, str], fail_on: Severity) -> bool:
    """True when any ``vuln.<bucket>`` count is > 0 at ``fail_on`` severity or above.

    ``unknown`` is treated as a lowest-rank catch-all: it is included in the gate
    whenever ``fail_on`` is ``low`` or ``unknown`` (i.e. the caller accepts uncertain findings).
    """
    members = list(Severity)
    at_or_above = set(members[: members.index(fail_on) + 1])
    # `unknown` ranks below `low`, so the at-or-above slice misses it. Fold it in only at the
    # two most permissive thresholds — `low` ("anything ranked") and `unknown` ("any finding").
    if fail_on in (Severity.low, Severity.unknown):
        at_or_above.add(Severity.unknown)
    return any(_count(facts.get(f"vuln.{s.value}")) > 0 for s in at_or_above)


def policy_breached(facts: dict[str, str]) -> bool:
    """True when any ``policy.<bucket>`` count is > 0 (a regis ``kind:"fail"`` verdict).

    Governance verdicts have no severity threshold here — *any* failing bucket breaches.
    The ``policy.passed`` receipt (regis ``kind:"pass"``) is **not** a breach.
    """
    return any(_count(facts.get(f"policy.{s.value}")) > 0 for s in Severity)


@dataclass(frozen=True)
class ScanSummary:
    """A normalized, format-specific scan summary.

    `facts` keys are namespaced by *finding type* (e.g. ``vuln.critical``), never by tool,
    so a query is tool-agnostic. The producing tool is carried separately as ``tool``.
    """

    tool: str
    tool_version: str
    facts: dict[str, str]


def build_scan_annotations(
    summary: ScanSummary,
    *,
    prefix: str,
    subject_digest: str,
    fmt: str,
    timestamp: datetime,
) -> dict[str, str]:
    """The `{prefix}.scan.*` annotation map for the referrer manifest.

    Honors an empty prefix (⇒ no summary annotations), mirroring stamp.py.
    """
    if not prefix:
        return {}
    out: dict[str, str] = {
        f"{prefix}.scan.tool": summary.tool,
        f"{prefix}.scan.format": fmt,
        f"{prefix}.scan.timestamp": timestamp.isoformat(),
        f"{prefix}.scan.subject": subject_digest,
    }
    if summary.tool_version:
        out[f"{prefix}.scan.tool.version"] = summary.tool_version
    for key, value in summary.facts.items():
        out[f"{prefix}.scan.{key}"] = value
    return out
