"""Build the provenance stamp annotations for a mirrored/derived artifact (§9).

OCI-standard annotations carry the immutable build facts every scanner reads for
free; `{prefix}.*` carries houba facts (owners key, artifact type, three-level
policy.import.variant identity). No location fact is stamped — the same digest can
live in many registries.
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
    source_revision: str | None,
    created: datetime,
    owners: list[str] | None,
    vendor: str | None = None,
    artifact_type: str,
    policy: str,
    import_name: str,
    variant: str,
    transform_steps: list[str] | None = None,
    transform_version_value: str | None = None,
) -> dict[str, str]:
    source = f"{source_registry}/{source_repository}"
    annotations: dict[str, str] = {
        # human-readable name = the upstream image's short name (so registry UIs read it for free)
        "org.opencontainers.image.title": source_repository.rsplit("/", 1)[-1],
        "org.opencontainers.image.source": source,
        "org.opencontainers.image.base.name": f"{source}:{source_tag}",
        "org.opencontainers.image.base.digest": source_digest,
        "org.opencontainers.image.created": created.isoformat(),
    }
    # vendor = the rebuilding org; org-specific so it is configuration, never hardcoded.
    if vendor:
        annotations["org.opencontainers.image.vendor"] = vendor
    # revision = the SCM revision of the *packaged software*, as the SOURCE image declares it
    # (OCI semantics). houba does not know the upstream commit, so it propagates the source's
    # own .revision when present and omits the key otherwise — never a fabricated digest/tag.
    if source_revision is not None:
        annotations["org.opencontainers.image.revision"] = source_revision
    if prefix:
        annotations[f"{prefix}.artifact.type"] = artifact_type
        annotations[f"{prefix}.policy"] = policy
        annotations[f"{prefix}.import"] = import_name
        annotations[f"{prefix}.variant"] = variant
        if owners:
            annotations[f"{prefix}.owners"] = ",".join(owners)
    if prefix and transform_steps and transform_version_value is not None:
        annotations[f"{prefix}.transform.steps"] = ",".join(transform_steps)
        annotations[f"{prefix}.transform.version"] = transform_version_value
    return annotations
