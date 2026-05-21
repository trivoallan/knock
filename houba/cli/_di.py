"""Composition root. Construit les adapters concrets à partir des Settings.

Volontairement non couvert par les tests unitaires (cf. coverage omit).
"""

from __future__ import annotations

from dataclasses import dataclass

from houba.adapters.harbor_http import HarborHttpAdapter
from houba.adapters.skopeo_cli import SkopeoAdapter
from houba.adapters.system_clock import SystemClock
from houba.config import Settings


@dataclass(frozen=True)
class Container:
    settings: Settings
    harbor: HarborHttpAdapter
    skopeo: SkopeoAdapter
    clock: SystemClock


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    harbor = HarborHttpAdapter(
        base_url=settings.harbor.url,
        user=settings.harbor.user,
        password=settings.harbor.password.get_secret_value(),
    )
    return Container(
        settings=settings,
        harbor=harbor,
        skopeo=SkopeoAdapter(),
        clock=SystemClock(),
    )
