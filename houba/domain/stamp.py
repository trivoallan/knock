"""Build the provenance stamp annotations for a mirrored/derived artifact (§9).

OCI-standard annotations carry the immutable build facts every scanner reads for
free; `{prefix}.*` carries houba facts (team owner key, artifact type, three-level
policy.import.variant identity). No location fact is stamped — the same digest can
live in many registries — and the human owner is resolved downstream from `team`.
"""

from __future__ import annotations

from datetime import datetime


def build_stamp_annotations(
    *,
    prefix: str,
    source_registry: str,
    source_repository: str,
    source_tag: str,
    source_digest: str,
    created: datetime,
    team: str | None,
    artifact_type: str,
    policy: str,
    import_name: str,
    variant: str,
) -> dict[str, str]:
    source = f"{source_registry}/{source_repository}"
    annotations: dict[str, str] = {
        "org.opencontainers.image.source": source,
        # revision = the immutable source digest (what was actually packaged),
        # not the mutable upstream tag. The tag survives in base.name.
        "org.opencontainers.image.revision": source_digest,
        "org.opencontainers.image.base.name": f"{source}:{source_tag}",
        "org.opencontainers.image.base.digest": source_digest,
        "org.opencontainers.image.created": created.isoformat(),
    }
    if prefix:
        annotations[f"{prefix}.artifact.type"] = artifact_type
        annotations[f"{prefix}.policy"] = policy
        annotations[f"{prefix}.import"] = import_name
        annotations[f"{prefix}.variant"] = variant
        if team is not None:
            annotations[f"{prefix}.owner.team"] = team
    return annotations
