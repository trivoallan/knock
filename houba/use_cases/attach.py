"""Ingest an upstream scan report and attach it as a stamped OCI referrer.

houba does not run a scanner: the report is produced upstream (CI / registry-native
scanner / scan service) and handed in. This use case resolves the subject digest,
normalizes the report to a summary, and attaches the raw report as a referrer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from houba.config import RegistryConfig, match_registry_by_host, resolve_registry
from houba.domain.scan.attestation import build_scan_statement
from houba.domain.scan.detect import resolve_format
from houba.domain.scan.formats.registry import DEFAULT_REGISTRY, Registry
from houba.domain.scan.refs import pin_to_digest
from houba.domain.scan.summary import Severity, build_scan_annotations, gate_breached
from houba.ports.attestor import AttestationRef, AttestorPort
from houba.ports.clock import ClockPort
from houba.ports.registry import RegistryPort
from houba.use_cases.registry_session import ensure_registry_session

SCAN_RESULT_ARTIFACT_TYPE = "application/vnd.houba.scan.result.v1"


@dataclass(frozen=True)
class ScanOutcome:
    subject_digest: str
    referrer_digest: str
    tool: str
    tool_version: str
    format: str
    facts: dict[str, str]
    timestamp: datetime
    attestation: AttestationRef | None = None


def attach_exit_code(outcome: ScanOutcome, *, fail_on: Severity | None) -> int:
    """1 when a severity gate is set and the scan breaches it, else 0."""
    if fail_on is not None and gate_breached(outcome.facts, fail_on):
        return 1
    return 0


def attach_scan(
    image_ref: str,
    report_bytes: bytes,
    *,
    registry: RegistryPort,
    clock: ClockPort,
    label_prefix: str,
    roster: dict[str, RegistryConfig] | None = None,
    registry_override: str | None = None,
    format_override: str | None = None,
    formats: Registry = DEFAULT_REGISTRY,
    attestor: AttestorPort | None = None,
    builder_id: str = "",
) -> ScanOutcome:
    roster = roster or {}
    if registry_override is not None:
        _name, cfg = resolve_registry(registry_override, roster)
        ensure_registry_session(registry, cfg, set())
    else:
        match = match_registry_by_host(image_ref, roster)
        if match is not None:
            ensure_registry_session(registry, match[1], set())
    info = registry.inspect(image_ref)
    subject = pin_to_digest(image_ref, info.digest)
    fmt = resolve_format(report_bytes, format_override, formats)
    mapper = formats.get(fmt)
    summary = mapper.summarize(report_bytes)
    now = clock.now()
    annotations = build_scan_annotations(
        summary, prefix=label_prefix, subject_digest=info.digest, fmt=fmt, timestamp=now
    )
    referrer = registry.put_referrer(
        subject,
        SCAN_RESULT_ARTIFACT_TYPE,
        annotations,
        blob=report_bytes,
        media_type=mapper.report_media_type,
    )
    attestation: AttestationRef | None = None
    if attestor is not None:
        statement = build_scan_statement(
            subject_name=image_ref,
            subject_digest=info.digest,
            scanner_name=summary.tool,
            scanner_version=summary.tool_version,
            fmt=fmt,
            summary=summary.facts,
            report_digest=referrer,
            attested_at=now.isoformat(),
            builder_id=builder_id,
        )
        attestation = attestor.attest(subject, statement)
    return ScanOutcome(
        subject_digest=info.digest,
        referrer_digest=referrer,
        tool=summary.tool,
        tool_version=summary.tool_version,
        format=fmt,
        facts=summary.facts,
        timestamp=now,
        attestation=attestation,
    )
