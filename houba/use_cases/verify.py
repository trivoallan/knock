"""Resolve a digest's facts (stamp annotations, SBOM referrers, verified scan predicates)
and evaluate them into a single pass/fail report. Read-only: no copy / annotate / put / delete.
"""

from __future__ import annotations

from datetime import timedelta

from houba.config import RegistryConfig, match_registry_by_host, resolve_registry
from houba.domain.scan.attestation import SCAN_PREDICATE_TYPE
from houba.domain.scan.refs import pin_to_digest
from houba.domain.scan.summary import Severity
from houba.domain.verify import Requirement, VerifyReport, evaluate
from houba.errors import ConfigError
from houba.ports.attestor import AttestorPort, VerifiedPredicate
from houba.ports.clock import ClockPort
from houba.ports.registry import RegistryPort
from houba.use_cases.registry_session import ensure_registry_session

_SBOM_TYPES = ("application/spdx+json", "application/vnd.cyclonedx+json")


def verify_exit_code(report: VerifyReport) -> int:
    return 0 if report.passed else 1


def verify_image(
    image_ref: str,
    *,
    requirements: set[Requirement],
    registry: RegistryPort,
    attestor: AttestorPort | None,
    clock: ClockPort,
    label_prefix: str,
    max_severity: Severity,
    max_age: timedelta,
    roster: dict[str, RegistryConfig] | None = None,
    registry_override: str | None = None,
) -> VerifyReport:
    roster = roster or {}
    if registry_override is not None:
        _name, cfg = resolve_registry(registry_override, roster)
        ensure_registry_session(registry, cfg, set())
    else:
        match = match_registry_by_host(image_ref, roster)
        if match is not None:
            ensure_registry_session(registry, match[1], set())

    digest, annotations = registry.get_annotations(image_ref)
    subject = pin_to_digest(image_ref, digest)

    stamp_present = bool(label_prefix) and f"{label_prefix}.artifact.type" in annotations

    sbom_present = False
    if Requirement.sbom in requirements:
        sbom_present = any(registry.list_referrers(subject, at) for at in _SBOM_TYPES)

    scan_predicates: list[VerifiedPredicate] = []
    if Requirement.scan_pass in requirements:
        if attestor is None:
            raise ConfigError(
                "houba verify --require scan-pass needs HOUBA_ATTEST_SIGNER configured"
            )
        scan_predicates = attestor.verify(subject, SCAN_PREDICATE_TYPE)

    return evaluate(
        requirements=requirements,
        stamp_present=stamp_present,
        sbom_present=sbom_present,
        scan_predicates=scan_predicates,
        max_severity=max_severity,
        max_age=max_age,
        now=clock.now(),
    )
