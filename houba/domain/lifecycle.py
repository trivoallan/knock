"""Pending-deletion marker payload (pure; sibling of stamp.py).

A `mark`-mode reconcile attaches this as an OCI referrer to the manifest of a tag
that fell out of the policy. `marked-at` is a FACT, not a deadline — the external
reaper owns timing. No location fact is recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

PENDING_DELETION_ARTIFACT_TYPE = "application/vnd.houba.lifecycle.pending+json"


def build_pending_deletion_annotations(
    *,
    prefix: str,
    marked_at: datetime,
    reason: str,
    policy: str,
    import_name: str,
    variant: str = "",
) -> dict[str, str]:
    lc = f"{prefix}.lifecycle" if prefix else "lifecycle"
    annotations: dict[str, str] = {
        f"{lc}.state": "pending-deletion",
        f"{lc}.marked-at": marked_at.isoformat(),
        f"{lc}.reason": reason,
    }
    if prefix:
        annotations[f"{prefix}.policy"] = policy
        annotations[f"{prefix}.import"] = import_name
        if variant:
            annotations[f"{prefix}.variant"] = variant
    return annotations


@dataclass(frozen=True)
class MarkIdentity:
    policy: str
    import_: str  # read-side field name; the writer's param is import_name
    variant: str


@dataclass(frozen=True)
class MarkedCandidate:
    image_ref: str
    identity: MarkIdentity
    marked_at: datetime | None
    reason: str


def _key(prefix: str, suffix: str) -> str:
    """`{prefix}.{suffix}` with the empty-prefix collapse the writer uses."""
    return f"{prefix}.{suffix}" if prefix else suffix


def _parse_marked_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_pending_mark(prefix: str, image_ref: str, annotations: dict[str, str]) -> MarkedCandidate:
    """Read a `pending-deletion` referrer's annotations back into a candidate.

    The exact inverse of `build_pending_deletion_annotations`; lenient on missing
    keys so a malformed mark never crashes the reaper's walk (it is still judged by
    its digest). `marked_at` is report/audit only.
    """
    return MarkedCandidate(
        image_ref=image_ref,
        identity=MarkIdentity(
            policy=annotations.get(_key(prefix, "policy"), ""),
            import_=annotations.get(_key(prefix, "import"), ""),
            variant=annotations.get(_key(prefix, "variant"), ""),
        ),
        marked_at=_parse_marked_at(annotations.get(_key(prefix, "lifecycle.marked-at"))),
        reason=annotations.get(_key(prefix, "lifecycle.reason"), ""),
    )
