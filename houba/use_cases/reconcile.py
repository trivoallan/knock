"""Reconcile use case: orchestrate selection → expand → reconcile → apply against
real registries via the RegistryPort (copy path). Depends only on ports.
"""

from __future__ import annotations

from datetime import datetime

from houba.domain.reconcile import MirrorArtifact, SourceArtifact
from houba.ports.registry import ImageInfo

BASE_DIGEST_KEY = "org.opencontainers.image.base.digest"


def to_source_artifact(info: ImageInfo, *, now: datetime) -> SourceArtifact:
    # Unknown created time → use `now` (conservative: treated as just-pushed, so the
    # 7-day stability window skips an update rather than churning on unknown freshness).
    return SourceArtifact(digest=info.digest, pushed_at=info.created or now)


def to_mirror_artifact(info: ImageInfo) -> MirrorArtifact | None:
    base = info.annotations.get(BASE_DIGEST_KEY)
    if base is None:
        return None
    return MirrorArtifact(base_digest=base)
