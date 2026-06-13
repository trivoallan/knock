"""Build the scan-result stamp annotations for an attached referrer (sibling of stamp.py).

OCI-standard facts are not re-emitted here (the image already carries them); this module
emits only the `{prefix}.scan.*` summary that makes a scan referrer queryable. The full
native report travels as the referrer blob, untouched. No I/O, no config.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


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
