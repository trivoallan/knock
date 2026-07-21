"""Build the in-toto Statement for knock's scan predicate (sign the attached scan result).

Sibling of `domain/attestation.py` (the transform predicate). Pure — no httpx / subprocess /
os.environ. knock is the *attester / ingester* here, not the scanner: `scanner` records the
upstream tool. The predicate is a Pydantic model so its JSON Schema is derived (never
hand-written) and frozen as public API at /v1.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from knock.domain.attestation import STATEMENT_TYPE

# Frozen public API: project-branded vanity URI, versioned at /v1 (same convention as the
# transform predicate). Needn't resolve; names no deploying org.
SCAN_PREDICATE_TYPE = "https://knock.dev/predicate/scan/v1"


class Scanner(BaseModel):
    """The upstream scanner that produced the report (knock did not run it)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str


class ScanPredicate(BaseModel):
    """knock's normalized scan summary — the signed, verifiable form of `io.knock.scan.*`."""

    model_config = ConfigDict(extra="forbid")

    scanner: Scanner
    format: str
    summary: dict[str, str]  # the io.knock.scan.* facts (prefix-less keys)
    report_digest: str  # digest of the raw SARIF referrer this attestation vouches for
    attested_at: str = Field(
        description=(
            "ISO-8601 timestamp of when knock attached and signed this scan. The "
            "freshness clock: an admission controller enforces a max-age policy "
            "against it (admit only if now - attested_at <= max-age). This signed "
            "field is the only trustworthy freshness source — not the unsigned "
            "scan-timestamp annotation (the KNOCK_LABEL_PREFIX-prefixed key, e.g. "
            "io.knock.scan.timestamp), which exists only for gc."
        )
    )
    builder_id: str  # knock as the attester


def _subject_digest(digest: str) -> dict[str, str]:
    """`sha256:abc` -> `{"sha256": "abc"}` (the in-toto subject digest shape)."""
    algo, sep, value = digest.partition(":")
    if not sep:
        return {"sha256": algo}  # no algo prefix -> assume sha256
    return {algo: value}


def build_scan_statement(
    *,
    subject_name: str,
    subject_digest: str,
    scanner_name: str,
    scanner_version: str,
    fmt: str,
    summary: dict[str, str],
    report_digest: str,
    attested_at: str,
    builder_id: str,
) -> dict[str, Any]:
    """Assemble the in-toto Statement whose subject is the scanned image digest.

    Pure: callers pass already-resolved facts. Returns a plain dict for an adapter to sign.
    """
    predicate = ScanPredicate(
        scanner=Scanner(name=scanner_name, version=scanner_version),
        format=fmt,
        summary=summary,
        report_digest=report_digest,
        attested_at=attested_at,
        builder_id=builder_id,
    )
    return {
        "_type": STATEMENT_TYPE,
        "subject": [{"name": subject_name, "digest": _subject_digest(subject_digest)}],
        "predicateType": SCAN_PREDICATE_TYPE,
        "predicate": predicate.model_dump(),
    }


def scan_predicate_json_schema() -> dict[str, Any]:
    """Published JSON Schema for the scan predicate (frozen public API /v1). Derived."""
    return ScanPredicate.model_json_schema()
