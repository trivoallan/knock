"""Composition root. Builds concrete adapters from the Settings.

Intentionally excluded from unit-test coverage (see coverage omit).
"""

from __future__ import annotations

from dataclasses import dataclass

from houba.adapters.buildkit_cli import BuildkitAdapter
from houba.adapters.command_scan import CommandScanAdapter
from houba.adapters.command_usage import CommandUsageAdapter
from houba.adapters.cosign_cli import CosignAdapter
from houba.adapters.regctl_cli import RegctlAdapter
from houba.adapters.structlog_reporter import StructlogReporter
from houba.adapters.syft_cli import SyftAdapter
from houba.adapters.system_clock import SystemClock
from houba.config import Settings
from houba.errors import ConfigError
from houba.ports.attestor import AttestorPort
from houba.ports.usage_oracle import UsageOraclePort
from houba.ports.vuln import VulnEvaluatorPort


@dataclass(frozen=True)
class Container:
    settings: Settings
    registry: RegctlAdapter
    builder: BuildkitAdapter
    clock: SystemClock
    reporter: StructlogReporter
    attestor: AttestorPort | None
    sbom_generator: SyftAdapter
    vuln_evaluator: VulnEvaluatorPort | None


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    attestor = CosignAdapter(settings.attest) if settings.attest_signer else None
    vuln_evaluator = (
        CommandScanAdapter(settings.scan_evaluator_cmd, settings.scan_evaluator_timeout)
        if settings.scan_evaluator_cmd
        else None
    )
    return Container(
        settings=settings,
        registry=RegctlAdapter(),
        builder=BuildkitAdapter(),
        clock=SystemClock(),
        reporter=StructlogReporter(),
        attestor=attestor,
        sbom_generator=SyftAdapter(),
        vuln_evaluator=vuln_evaluator,
    )


def build_usage_oracle(settings: Settings) -> UsageOraclePort:
    """Lazy, purge-only: reconcile never constructs this, so its config stays optional."""
    if settings.usage_oracle_cmd is None:
        raise ConfigError("houba purge requires HOUBA_USAGE_ORACLE_CMD (the usage oracle command)")
    return CommandUsageAdapter(settings.usage_oracle_cmd, settings.usage_oracle_timeout)
