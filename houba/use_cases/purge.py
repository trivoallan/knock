"""The reference reaper driver (§7): scan pending marks, judge by prod usage, purge.

Isolated from reconcile's orchestration — reuses only RegistryPort. Fail-closed:
oracle error / uncertainty => protect. Partial-failure: per-candidate hard errors
are recorded and redden the exit; they never block siblings. The catalog walk is
SEQUENTIAL in v1.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from houba.config import RegistryConfig, resolve_registry
from houba.domain.lifecycle import PENDING_DELETION_ARTIFACT_TYPE, parse_pending_mark
from houba.domain.purge import PurgeDecision, decide_purge, usage_window_start
from houba.errors import HoubaError, exit_code_for
from houba.ports.registry import Referrer, RegistryPort
from houba.ports.reporter import ErrorInfo
from houba.ports.usage_oracle import UsageOraclePort, UsageQuery

PurgeMode = Literal["apply", "dry-run"]


class PurgeOutcome(BaseModel):
    image_ref: str
    digest: str | None = None
    decision: str | None = None  # "purge" | "protect" | "uncertain"
    reason: str = ""
    applied: bool = False
    error: ErrorInfo | None = None  # set => a hard failure processing this candidate


class PurgeReport(BaseModel):
    mode: PurgeMode
    outcomes: list[PurgeOutcome]


def purge_exit_code(report: PurgeReport) -> int:
    """0 unless a candidate hit a hard error; then the worst failure exit code."""
    codes = [o.error.exit_code for o in report.outcomes if o.error is not None]
    return max(codes) if codes else 0


def _err(exc: BaseException) -> ErrorInfo:
    return ErrorInfo(type=type(exc).__name__, message=str(exc), exit_code=exit_code_for(exc))


def purge_marks(
    *,
    registry: RegistryPort,
    oracle: UsageOraclePort,
    roster: dict[str, RegistryConfig],
    only_registry: str | None,
    label_prefix: str,
    min_idle_days: int,
    now: datetime,
    apply: bool,
) -> PurgeReport:
    mode: PurgeMode = "apply" if apply else "dry-run"
    since = usage_window_start(now, timedelta(days=min_idle_days))

    if only_registry is not None:
        name, cfg = resolve_registry(only_registry, roster)
        targets = [(name, cfg)]
    else:
        targets = list(roster.items())

    outcomes: list[PurgeOutcome] = []
    logged_in: set[str] = set()
    for _name, cfg in targets:
        if cfg.host not in logged_in:
            registry.configure_registry(cfg.host, tls_verify=cfg.tls_verify, ca_cert=cfg.ca_cert)
            if cfg.username is not None and cfg.password is not None:
                registry.login(
                    cfg.host,
                    username=cfg.username,
                    password=cfg.password.get_secret_value(),
                    tls_verify=cfg.tls_verify,
                )
            logged_in.add(cfg.host)
        for repo in registry.list_repositories(cfg.host):
            repo_ref = f"{cfg.host}/{repo}"
            for tag in registry.list_tags(repo_ref):
                image_ref = f"{repo_ref}:{tag}"
                for ref in registry.list_referrers(image_ref, PENDING_DELETION_ARTIFACT_TYPE):
                    outcomes.append(
                        _process(
                            repo_ref=repo_ref,
                            image_ref=image_ref,
                            referrer=ref,
                            registry=registry,
                            oracle=oracle,
                            label_prefix=label_prefix,
                            since=since,
                            apply=apply,
                        )
                    )
    return PurgeReport(mode=mode, outcomes=outcomes)


def _process(
    *,
    repo_ref: str,
    image_ref: str,
    referrer: Referrer,
    registry: RegistryPort,
    oracle: UsageOraclePort,
    label_prefix: str,
    since: datetime,
    apply: bool,
) -> PurgeOutcome:
    candidate = parse_pending_mark(label_prefix, image_ref, referrer.annotations)
    try:
        digest = registry.inspect(image_ref).digest
    except HoubaError as exc:
        return PurgeOutcome(image_ref=image_ref, error=_err(exc))

    try:
        observation = oracle.last_prod_usage(
            UsageQuery(digest=digest, image_ref=image_ref, identity=candidate.identity, since=since)
        )
        decision = decide_purge(observation.last_seen, observed=True)
        reason = observation.detail
    except HoubaError:
        decision = decide_purge(None, observed=False)  # fail-closed: oracle error => protect
        reason = "usage oracle unavailable"

    if decision is not PurgeDecision.purge:
        return PurgeOutcome(
            image_ref=image_ref, digest=digest, decision=decision.value, reason=reason
        )
    if not apply:
        return PurgeOutcome(image_ref=image_ref, digest=digest, decision="purge", reason=reason)
    try:
        registry.delete_tag(image_ref)
        registry.delete_referrer(f"{repo_ref}@{referrer.digest}")
    except HoubaError as exc:
        return PurgeOutcome(
            image_ref=image_ref, digest=digest, decision="purge", reason=reason, error=_err(exc)
        )
    return PurgeOutcome(
        image_ref=image_ref, digest=digest, decision="purge", reason=reason, applied=True
    )
