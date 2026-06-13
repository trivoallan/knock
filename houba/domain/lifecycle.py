"""Pending-deletion marker payload (pure; sibling of stamp.py).

A `mark`-mode reconcile attaches this as an OCI referrer to the manifest of a tag
that fell out of the policy. `marked-at` is a FACT, not a deadline — the external
reaper owns timing. No location fact is recorded.
"""

from __future__ import annotations

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
