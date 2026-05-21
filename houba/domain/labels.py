"""Construction des labels OCI fr.sncf.h2h.* apposés sur les images importées."""

from __future__ import annotations

from datetime import datetime


def build_labels(
    *,
    src_registry: str,
    src_repository: str,
    src_tag: str,
    src_digest: str,
    import_date: datetime,
    harbor: str,
    eol_product: str | None,
    eol_date: str | None,
) -> dict[str, str]:
    labels: dict[str, str] = {
        "fr.sncf.h2h.source.registry": src_registry,
        "fr.sncf.h2h.source.repository": src_repository,
        "fr.sncf.h2h.source.tag": src_tag,
        "fr.sncf.h2h.source.digest": src_digest,
        "fr.sncf.h2h.import.date": import_date.isoformat(),
        "fr.sncf.h2h.import.harbor": harbor,
    }
    if eol_product:
        labels["fr.sncf.h2h.eol.product"] = eol_product
    if eol_date:
        labels["fr.sncf.h2h.eol.date"] = eol_date
    return labels
