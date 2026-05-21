"""Construction d'un plan d'import pour un tag donné.

Le plan agrège toutes les informations nécessaires au use-case product_import
pour générer un Dockerfile et exécuter BuildKit. C'est une valeur, pas un acteur.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from houba.domain.labels import build_labels
from houba.domain.properties import Properties


@dataclass(frozen=True)
class ImportPlan:
    tag: str
    src_image: str  # "<registry>/<repository>:<tag>"
    dst_image: str  # "<project>/<repository>:<tag>"
    src_digest: str
    flags: dict[str, bool]
    labels: dict[str, str]


def build_plan(
    *,
    tag: str,
    properties: Properties,
    src_digest: str,
    eol_date: str | None,
    now: datetime,
) -> ImportPlan:
    src_image = f"{properties.source.registry}/{properties.source.repository}:{tag}"
    dst_image = f"{properties.destination.project}/{properties.destination.repository}:{tag}"

    flags = properties.flags.model_dump()

    labels = build_labels(
        src_registry=properties.source.registry,
        src_repository=properties.source.repository,
        src_tag=tag,
        src_digest=src_digest,
        import_date=now,
        harbor=properties.destination.harbor,
        eol_product=properties.eol.product,
        eol_date=eol_date,
    )

    return ImportPlan(
        tag=tag,
        src_image=src_image,
        dst_image=dst_image,
        src_digest=src_digest,
        flags=flags,
        labels=labels,
    )
