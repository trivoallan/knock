"""Lecture de la configuration depuis les variables d'environnement.

Aucun autre module ne doit lire directement os.environ.
Voir spec §6.1.

Architecture : chaque sous-bloc est un `BaseSettings` avec son propre
`env_prefix`. Le bloc racine les compose via `default_factory`. Cela
préserve le contrat single-underscore du spec (`H2H_HARBOR_URL` plutôt
que `H2H_HARBOR__URL`) tout en gardant l'API ergonomique
`settings.harbor.url`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class HarborSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="H2H_HARBOR_",
        env_file=None,
        extra="ignore",
    )

    url: str
    user: str
    password: SecretStr
    project_default: str | None = None


class HarborOrangeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="H2H_HARBOR_ORANGE_",
        env_file=None,
        extra="ignore",
    )

    url: str | None = None
    user: str | None = None
    password: SecretStr | None = None


class GitLabSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="H2H_GITLAB_",
        env_file=None,
        extra="ignore",
    )

    url: str
    token: SecretStr
    group: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="H2H_",
        env_file=None,
        extra="ignore",
    )

    harbor: HarborSettings = Field(default_factory=HarborSettings)  # type: ignore[arg-type]
    harbor_orange: HarborOrangeSettings = Field(default_factory=HarborOrangeSettings)
    gitlab: GitLabSettings = Field(default_factory=GitLabSettings)  # type: ignore[arg-type]

    teams_webhook_url: SecretStr | None = None
    endoflife_url: HttpUrl = HttpUrl("https://endoflife.date/api")

    log_format: Literal["text", "json"] = "text"
    log_level: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR"] = "INFO"
    dry_run_tags: bool = False
    dry_run_deletions: bool = False
    work_dir: Path = Path("/tmp/h2h-work")  # noqa: S108

    project: str | None = None
    repository: str | None = None
