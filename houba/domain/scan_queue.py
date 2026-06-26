"""Pure decision logic for the scan pipeline. NO `import redis` here — these are
unit-tested without a broker; the Redis I/O lives in scan_streams.py."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


def enqueue_refs(report: dict[str, Any]) -> list[str]:
    """Placed digests = applied variant operations carrying an out_digest.

    Tree: run -> policies[] -> targets[] -> variants[] -> operations[]. The ref is
    `TargetReport.dest_repo @ Operation.out_digest`; dest_repo is ALREADY host-qualified
    (Operation has no out_repo), so never re-prefix the host.
    """
    refs: list[str] = []
    for policy in report.get("policies", []):
        for target in policy.get("targets", []):
            dest_repo = target["dest_repo"]
            for variant in target.get("variants", []):
                for op in variant.get("operations", []):
                    if op.get("applied") and op.get("out_digest"):
                        refs.append(f"{dest_repo}@{op['out_digest']}")
    return refs


def should_dead_letter(delivery_count: int, max_deliveries: int) -> bool:
    """Route to the dead stream only AFTER max_deliveries attempts (strictly greater)."""
    return delivery_count > max_deliveries


@dataclass(frozen=True)
class Failure:
    kind: str  # "transient" (retry/replay) | "permanent" (drop, do not retry)
    suggested_action: str  # problem + cause + fix, for the operator (scan-dlq show)


# Ordered (first match wins): permanent markers before the transient default.
_PERMANENT = ("manifest unknown", "404", "not found", "name unknown")
_SIGNER = ("no signer", "houba_attest_signer", "cosignerror")


def classify_failure(stage: str, exit_code: int, stderr: str) -> Failure:
    """F5: an image deleted before scan fails PERMANENTLY (drop, not dead-letter-as-transient);
    everything else is transient (replay). The result drives both the dead-letter-vs-drop
    decision and the operator's `suggested_action`."""
    s = stderr.lower()
    if any(m in s for m in _PERMANENT):
        return Failure("permanent", f"{stage}: image gone (manifest 404) -> drop, do not retry")
    if any(m in s for m in _SIGNER):
        return Failure(
            "transient", f"{stage}: signer error -> check HOUBA_ATTEST_SIGNER, then replay"
        )
    return Failure(
        "transient", f"{stage} failed (see error) -> likely transient (registry 5xx); replay"
    )


# Exception-type names whose presence alone marks a signer failure, regardless of
# message text (the attach stage raises these by type, not stderr).
_SIGNER_TYPES = ("CosignError",)


def classify_exception(stage: str, exc_type: str, message: str) -> Failure:
    """Failure policy for the in-process stages that raise typed exceptions instead
    of producing CLI stderr. Shares the transient/permanent verdict strings with
    classify_failure. Domain stays import-free of the adapter error classes: callers
    pass type(exc).__name__ and str(exc)."""
    s = message.lower()
    if any(m in s for m in _PERMANENT):
        return Failure("permanent", f"{stage}: image gone (manifest 404) -> drop, do not retry")
    if exc_type in _SIGNER_TYPES or any(m in s for m in _SIGNER):
        return Failure(
            "transient", f"{stage}: signer error -> check HOUBA_ATTEST_SIGNER, then replay"
        )
    return Failure(
        "transient", f"{stage} raised {exc_type} -> likely transient (registry 5xx); replay"
    )


def coverage_gap(placed: set[str], fresh_confirmed: set[str]) -> list[str]:
    """The supply-chain anchor: digests placed but not freshly scan-confirmed.
    A non-empty result = images the pipe silently dropped (or whose scan went stale)."""
    return list(placed - fresh_confirmed)


def gap_by_owner(gap: list[str], owners: dict[str, str]) -> dict[str, int]:
    """Join each uncovered digest to the stamp's owner (Backstage entity-ref) so the
    metric is actionable: '12 uncovered, team-x (5), team-y (7)', not an anonymous N.
    Producer-side only (a metric label) — NOT the coverage portal."""
    return dict(Counter(owners.get(d, "<unknown>") for d in gap))
