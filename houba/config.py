"""Lecture de la configuration depuis les variables d'environnement.

Aucun autre module ne doit lire directement os.environ.
Voir spec §6.1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from houba.errors import ConfigError


class RegistryConfig(BaseModel):
    """One real registry behind a logical destination name (host + credentials)."""

    model_config = ConfigDict(extra="forbid")

    host: str  # registry host, e.g. "harbor.corp.example.com" or "localhost:5000"
    username: str | None = None
    password: SecretStr | None = None
    tls_verify: bool = True

    @model_validator(mode="after")
    def _credentials_both_or_neither(self) -> RegistryConfig:
        if (self.username is None) != (self.password is None):
            raise ValueError("registry username and password must be set together")
        return self


class CACertSource(BaseModel):
    """A CA certificate supplied either as a filesystem path or as an inline PEM string."""

    model_config = ConfigDict(extra="forbid")

    path: str | None = None
    pem: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> CACertSource:
        if (self.path is None) == (self.pem is None):
            raise ValueError("a CA cert source needs exactly one of path | pem")
        return self


class PackageMirror(BaseModel):
    """Override URLs for one or more OS package managers during image hardening."""

    model_config = ConfigDict(extra="forbid")

    apt: str | None = None
    apk: str | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> PackageMirror:
        if self.apt is None and self.apk is None:
            raise ValueError("a package mirror needs at least one of apt | apk")
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOUBA_",
        env_file=None,
        extra="ignore",
    )

    label_prefix: str = "io.houba"
    registries: dict[str, RegistryConfig] = Field(default_factory=dict)

    log_format: Literal["text", "json"] = "text"
    log_level: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR"] = "INFO"
    dry_run_tags: bool = False
    dry_run_deletions: bool = False
    work_dir: Path = Path("/tmp/houba-work")  # noqa: S108

    transform_ca_certs: dict[str, CACertSource] = Field(default_factory=dict)
    transform_package_mirrors: dict[str, PackageMirror] = Field(default_factory=dict)
    build_platform: str = "linux/amd64"


def resolve_registry(
    name: str | None, roster: dict[str, RegistryConfig]
) -> tuple[str, RegistryConfig]:
    """Resolve a destination's logical registry name against the roster.

    A name is looked up directly. When omitted (`None`), it resolves to the sole
    configured registry — but only if exactly one is configured; zero or several
    is a ConfigError (spec §7, "optional iff exactly one registry configured").
    """
    if name is not None:
        try:
            return name, roster[name]
        except KeyError:
            raise ConfigError(f"unknown registry {name!r}; configured: {sorted(roster)}") from None
    if len(roster) == 1:
        only = next(iter(roster))
        return only, roster[only]
    if not roster:
        raise ConfigError("no registries configured (set HOUBA_REGISTRIES)")
    raise ConfigError(
        f"destination registry omitted but {len(roster)} configured; "
        f"specify one of {sorted(roster)}"
    )


def resolve_ca_certs(
    names: list[str], roster: dict[str, CACertSource]
) -> list[tuple[str, CACertSource]]:
    """Resolve a list of CA cert names against the configured roster."""
    out: list[tuple[str, CACertSource]] = []
    for name in names:
        try:
            out.append((name, roster[name]))
        except KeyError:
            raise ConfigError(f"unknown CA cert {name!r}; configured: {sorted(roster)}") from None
    return out


def resolve_mirror(name: str, roster: dict[str, PackageMirror]) -> PackageMirror:
    """Resolve a package mirror name against the configured roster."""
    try:
        return roster[name]
    except KeyError:
        raise ConfigError(
            f"unknown package mirror {name!r}; configured: {sorted(roster)}"
        ) from None
