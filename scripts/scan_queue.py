"""Pure decision logic for the scan pipeline. NO `import redis` here — these are
unit-tested without a broker; the Redis I/O lives in scan_streams.py."""

from __future__ import annotations


def enqueue_refs(report: dict) -> list[str]:
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
