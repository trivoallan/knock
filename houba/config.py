"""Lecture de la configuration depuis les variables d'environnement.

Aucun autre module ne doit lire directement os.environ.
Voir spec §6.1.

Architecture : chaque sous-bloc est un `BaseSettings` avec son propre
`env_prefix`. Le bloc racine les compose via `default_factory`. Cela
préserve le contrat single-underscore du spec (`HOUBA_HARBOR_URL` plutôt
que `HOUBA_HARBOR__URL`) tout en gardant l'API ergonomique
`settings.harbor.url`.
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


class HarborSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOUBA_HARBOR_",
        env_file=None,
        extra="ignore",
    )

    url: str
    user: str
    password: SecretStr
    project_default: str | None = None


class GitLabSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOUBA_GITLAB_",
        env_file=None,
        extra="ignore",
    )

    url: str
    token: SecretStr
    group: str


def _build_harbor() -> HarborSettings:
    return HarborSettings.model_validate({})


def _build_gitlab() -> GitLabSettings:
    return GitLabSettings.model_validate({})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOUBA_",
        env_file=None,
        extra="ignore",
    )

    harbor: HarborSettings = Field(default_factory=_build_harbor)
    gitlab: GitLabSettings = Field(default_factory=_build_gitlab)

    teams_webhook_url: SecretStr | None = None
    label_prefix: str = "io.houba"
    registries: dict[str, RegistryConfig] = Field(default_factory=dict)

    log_format: Literal["text", "json"] = "text"
    log_level: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR"] = "INFO"
    dry_run_tags: bool = False
    dry_run_deletions: bool = False
    work_dir: Path = Path("/tmp/houba-work")  # noqa: S108

    project: str | None = None
    repository: str | None = None


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
