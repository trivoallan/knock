"""Coverage audit (roadmap ④): catalog-walk the registry and report images that do NOT
carry houba's provenance stamp. Read-only; depends only on RegistryPort. Sequential v1,
structurally a sibling of `use_cases/purge.py`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from houba.config import RegistryConfig, resolve_registry
from houba.domain.attestation import COSIGN_ATTESTATION_ARTIFACT_TYPE
from houba.domain.coverage import is_stamped
from houba.errors import HoubaError, exit_code_for
from houba.ports.registry import RegistryPort
from houba.ports.reporter import ErrorInfo
from houba.use_cases.registry_session import ensure_registry_session


class CoverageOutcome(BaseModel):
    image_ref: str
    covered: bool = False
    signed: bool | None = None  # None = not probed; set only for covered images when check_signed
    policy: str | None = None  # {prefix}.policy when covered & present (audit context)
    error: ErrorInfo | None = None  # set => a hard failure reading this image


class CoverageCounts(BaseModel):
    scanned: int = 0
    covered: int = 0
    uncovered: int = 0
    signed: int = 0
    unsigned: int = 0
    errored: int = 0


class CoverageReport(BaseModel):
    registries: list[str]
    counts: CoverageCounts
    outcomes: list[CoverageOutcome]


def coverage_report_json_schema() -> dict[str, Any]:
    """Published JSON Schema for the coverage report (derived, never hand-written)."""
    return CoverageReport.model_json_schema()


def audit_exit_code(report: CoverageReport, *, fail_on_uncovered: bool) -> int:
    """Worst per-image read-error code if any; else 1 when gating on a non-empty gap; else 0."""
    codes = [o.error.exit_code for o in report.outcomes if o.error is not None]
    if codes:
        return max(codes)
    if fail_on_uncovered and report.counts.uncovered > 0:
        return 1
    return 0


def _err(exc: BaseException) -> ErrorInfo:
    return ErrorInfo(type=type(exc).__name__, message=str(exc), exit_code=exit_code_for(exc))


def _classify(
    image_ref: str, *, registry: RegistryPort, label_prefix: str, check_signed: bool
) -> CoverageOutcome:
    try:
        annotations = registry.get_annotations(image_ref)
        covered = is_stamped(annotations, prefix=label_prefix)
        policy = annotations.get(f"{label_prefix}.policy") if (covered and label_prefix) else None
        signed: bool | None = None
        if check_signed and covered:
            signed = bool(registry.list_referrers(image_ref, COSIGN_ATTESTATION_ARTIFACT_TYPE))
        return CoverageOutcome(image_ref=image_ref, covered=covered, signed=signed, policy=policy)
    except HoubaError as exc:
        return CoverageOutcome(image_ref=image_ref, error=_err(exc))


def audit_coverage(
    *,
    registry: RegistryPort,
    roster: dict[str, RegistryConfig],
    only_registry: str | None,
    label_prefix: str,
    check_signed: bool = False,
) -> CoverageReport:
    if only_registry is not None:
        name, cfg = resolve_registry(only_registry, roster)
        targets = [(name, cfg)]
    else:
        targets = list(roster.items())

    outcomes: list[CoverageOutcome] = []
    logged_in: set[str] = set()
    for _name, cfg in targets:
        ensure_registry_session(registry, cfg, logged_in)
        for repo in registry.list_repositories(cfg.host):
            repo_ref = f"{cfg.host}/{repo}"
            for tag in registry.list_tags(repo_ref):
                outcomes.append(
                    _classify(
                        f"{repo_ref}:{tag}",
                        registry=registry,
                        label_prefix=label_prefix,
                        check_signed=check_signed,
                    )
                )

    counts = CoverageCounts(
        scanned=len(outcomes),
        covered=sum(1 for o in outcomes if o.error is None and o.covered),
        uncovered=sum(1 for o in outcomes if o.error is None and not o.covered),
        signed=sum(1 for o in outcomes if o.signed is True),
        unsigned=sum(1 for o in outcomes if o.signed is False),
        errored=sum(1 for o in outcomes if o.error is not None),
    )
    return CoverageReport(
        registries=[cfg.host for _name, cfg in targets], counts=counts, outcomes=outcomes
    )
