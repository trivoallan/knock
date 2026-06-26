"""Composition root. Builds concrete adapters from the Settings.

Intentionally excluded from unit-test coverage (see coverage omit).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from houba.adapters.buildkit_cli import BuildkitAdapter
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


@dataclass(frozen=True)
class Container:
    settings: Settings
    registry: RegctlAdapter
    builder: BuildkitAdapter
    clock: SystemClock
    reporter: StructlogReporter
    attestor: AttestorPort | None
    sbom_generator: SyftAdapter


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    attestor = CosignAdapter(settings.attest) if settings.attest_signer else None
    return Container(
        settings=settings,
        registry=RegctlAdapter(),
        builder=BuildkitAdapter(),
        clock=SystemClock(),
        reporter=StructlogReporter(),
        attestor=attestor,
        sbom_generator=SyftAdapter(),
    )


def build_usage_oracle(settings: Settings) -> UsageOraclePort:
    """Lazy, purge-only: reconcile never constructs this, so its config stays optional."""
    if settings.usage_oracle_cmd is None:
        raise ConfigError("houba purge requires HOUBA_USAGE_ORACLE_CMD (the usage oracle command)")
    return CommandUsageAdapter(settings.usage_oracle_cmd, settings.usage_oracle_timeout)


def build_scan_adapter() -> Any:
    """Build the RedisStreamsAdapter from env config.  Imported lazily — redis-py must
    be installed (``pip install houba[scan]``) before calling this."""
    import os

    import redis

    from houba.adapters.redis_streams import RedisStreamsAdapter
    from houba.config import scan_redis_from_env

    cfg = scan_redis_from_env()
    host, port = cfg.addr.rsplit(":", 1)
    client = redis.Redis(host=host, port=int(port), decode_responses=True)
    consumer = os.environ.get("HOSTNAME", "worker")  # HOSTNAME = pod name in k8s
    return RedisStreamsAdapter(
        client,
        consumer=consumer,
        work=cfg.work,
        dead=cfg.dead,
        confirmed=cfg.confirmed,
        placed=cfg.placed,
        group=cfg.group,
    )


def build_scan_and_attach() -> Callable[[str], Any]:
    """Build the scan_and_attach closure, wiring the standard ports the same way
    cli/attach.py does."""
    import os

    from houba.use_cases.scan_worker import make_scan_and_attach

    container = build_container()
    return make_scan_and_attach(
        registry=container.registry,
        clock=container.clock,
        label_prefix=container.settings.label_prefix,
        sarif_path=os.environ.get("HOUBA_SCAN_SARIF_PATH", "/shared/scan.sarif"),
        roster=container.settings.registries,
        attestor=container.attestor,
    )
