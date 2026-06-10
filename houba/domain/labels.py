"""Construction des labels OCI (préfixe configurable) apposés sur les images importées."""

from __future__ import annotations

from datetime import datetime


def build_labels(
    *,
    prefix: str,
    src_registry: str,
    src_repository: str,
    src_tag: str,
    src_digest: str,
    import_date: datetime,
    harbor: str,
) -> dict[str, str]:
    if not prefix:
        return {}
    labels: dict[str, str] = {
        f"{prefix}.source.registry": src_registry,
        f"{prefix}.source.repository": src_repository,
        f"{prefix}.source.tag": src_tag,
        f"{prefix}.source.digest": src_digest,
        f"{prefix}.import.date": import_date.isoformat(),
        f"{prefix}.import.harbor": harbor,
    }
    return labels
