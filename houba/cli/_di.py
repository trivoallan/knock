"""Composition root. Construit les adapters concrets à partir des Settings.

Volontairement non couvert par les tests unitaires (cf. coverage omit).
"""

from __future__ import annotations

from dataclasses import dataclass

from houba.adapters.buildkit_cli import BuildkitAdapter
from houba.adapters.regctl_cli import RegctlAdapter
from houba.adapters.structlog_reporter import StructlogReporter
from houba.adapters.system_clock import SystemClock
from houba.config import Settings


@dataclass(frozen=True)
class Container:
    settings: Settings
    registry: RegctlAdapter
    builder: BuildkitAdapter
    clock: SystemClock
    reporter: StructlogReporter


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    return Container(
        settings=settings,
        registry=RegctlAdapter(),
        builder=BuildkitAdapter(),
        clock=SystemClock(),
        reporter=StructlogReporter(),
    )
