"""Shared registry-session setup: configure TLS/CA then log in, once per host.

reconcile, audit, and attach all need a registry authenticated and TLS-configured
before they touch it. This is the single place that block lives.
"""

from __future__ import annotations

from houba.config import RegistryConfig
from houba.ports.registry import RegistryPort


def ensure_registry_session(
    registry: RegistryPort, cfg: RegistryConfig, logged_in: set[str]
) -> None:
    """Configure and (if credentials are set) log into cfg.host, at most once.

    `logged_in` is the caller-owned set of hosts already set up; this function
    adds cfg.host to it. Idempotent: a host already in the set is a no-op.
    """
    if cfg.host in logged_in:
        return
    registry.configure_registry(cfg.host, tls_verify=cfg.tls_verify, ca_cert=cfg.ca_cert)
    if cfg.username is not None and cfg.password is not None:
        registry.login(
            cfg.host,
            username=cfg.username,
            password=cfg.password.get_secret_value(),
            tls_verify=cfg.tls_verify,
        )
    logged_in.add(cfg.host)
