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
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _validate_http_url(value: str) -> str:
    """Valide la valeur comme URL via Pydantic mais expose une `str`.

    Les consommateurs downstream (httpx, urllib.parse.urljoin) attendent une
    `str`, pas un wrapper `HttpUrl`. On valide à la lecture de la config puis on
    stocke la chaîne brute.
    """
    HttpUrl(value)  # lève ValidationError si malformée
    return value


HttpUrlStr = Annotated[str, AfterValidator(_validate_http_url)]


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


class HarborOrangeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOUBA_HARBOR_ORANGE_",
        env_file=None,
        extra="ignore",
    )

    url: str | None = None
    user: str | None = None
    password: SecretStr | None = None


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


def _build_harbor_orange() -> HarborOrangeSettings:
    return HarborOrangeSettings.model_validate({})


def _build_gitlab() -> GitLabSettings:
    return GitLabSettings.model_validate({})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOUBA_",
        env_file=None,
        extra="ignore",
    )

    harbor: HarborSettings = Field(default_factory=_build_harbor)
    harbor_orange: HarborOrangeSettings = Field(default_factory=_build_harbor_orange)
    gitlab: GitLabSettings = Field(default_factory=_build_gitlab)

    teams_webhook_url: SecretStr | None = None
    endoflife_url: HttpUrlStr = "https://endoflife.date/api"

    log_format: Literal["text", "json"] = "text"
    log_level: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR"] = "INFO"
    dry_run_tags: bool = False
    dry_run_deletions: bool = False
    work_dir: Path = Path("/tmp/h2h-work")  # noqa: S108

    project: str | None = None
    repository: str | None = None
