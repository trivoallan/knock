# Phase A — Fondations + couche `domain/` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Établir le squelette Python du paquet `hub2hub`, capturer des fixtures de production via une commande `h2h dev capture`, et porter en Python pur (avec tests > 90 %) toute la logique métier extraite du Groovy.

**Architecture:** Package Python en architecture hexagonale (`domain/`, `ports/`, `adapters/`, `use_cases/`, `cli/`). Cette phase ne livre que `domain/` complet, plus le strict minimum d'adaptateurs en lecture pour la capture de fixtures. Aucun chemin d'écriture vers Harbor/GitLab/Teams n'est implémenté ici.

**Tech Stack:** Python 3.12, uv (gestionnaire de projet), ruff (lint + format), mypy --strict, pytest + pytest-cov + hypothesis + syrupy + respx, pydantic v2, structlog, typer, httpx, jinja2.

**Branche de travail :** `feat/python-cli` (créer en J+0 depuis `master`).

**Référence spec :** [docs/superpowers/specs/2026-05-21-refactor-groovy-to-python-cli-design.md](../specs/2026-05-21-refactor-groovy-to-python-cli-design.md)

---

## Carte des fichiers créés en Phase A

```
pyproject.toml
uv.lock
.python-version
ruff.toml                          (ou config dans pyproject.toml)
.gitlab-ci.yml                     (modifié : ajout de jobs Python)
Dockerfile                         (squelette d'image — pas encore le runtime complet)

hub2hub/
├── __init__.py
├── config.py                      Pydantic Settings (env vars)
├── errors.py                      Hiérarchie d'exceptions + exit codes
├── logging.py                     Setup structlog
├── domain/
│   ├── __init__.py
│   ├── semver.py
│   ├── properties.py
│   ├── labels.py
│   ├── eol.py
│   ├── tag_filter.py
│   ├── purge.py
│   └── plan.py
├── ports/
│   ├── __init__.py
│   ├── harbor.py                  (read-only subset)
│   ├── source_registry.py
│   └── clock.py
├── adapters/
│   ├── __init__.py
│   ├── harbor_http.py             (read-only : GET projets, repositories, artifacts)
│   ├── skopeo_cli.py              (inspect, list-tags)
│   └── system_clock.py
├── cli/
│   ├── __init__.py
│   ├── main.py                    typer root + version + harbor health
│   ├── dev.py                     h2h dev capture
│   └── _di.py                     composition root
└── resources/
    └── (vide en Phase A — sera rempli en Phase B/C)

tests/
├── conftest.py
├── fakes/
│   ├── __init__.py
│   ├── harbor.py                  FakeHarborPort
│   ├── source_registry.py         FakeSourceRegistryPort
│   └── clock.py                   FakeClock
├── fake-bins/                     binaires shell mockés
│   ├── skopeo
│   └── git
├── fixtures/
│   ├── captured/                  rempli manuellement via h2h dev capture
│   └── synthetic/                 fixtures écrites à la main pour TDD
├── unit/
│   ├── domain/
│   │   ├── test_semver.py
│   │   ├── test_properties.py
│   │   ├── test_labels.py
│   │   ├── test_eol.py
│   │   ├── test_tag_filter.py
│   │   ├── test_purge.py
│   │   └── test_plan.py
│   ├── test_config.py
│   ├── test_errors.py
│   └── test_logging.py
└── integration/
    ├── test_harbor_http.py
    ├── test_skopeo_cli.py
    └── test_cli_dev_capture.py
```

---

## Groupe 1 — Squelette projet

### Task 1 : Initialiser `pyproject.toml`, `uv` et structure de base

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore` (ajout d'entrées Python)
- Create: `hub2hub/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1 : Créer `.python-version`**

```
3.12
```

- [ ] **Step 2 : Écrire `pyproject.toml`**

```toml
[project]
name = "hub2hub"
version = "0.1.0-dev"
description = "Hub2Hub CLI — mirroring Docker images into SNCF Harbor"
requires-python = ">=3.12,<3.13"
dependencies = [
    "httpx>=0.27",
    "jinja2>=3.1",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "structlog>=24.1",
    "tenacity>=8.3",
    "typer>=0.12",
]

[project.scripts]
h2h = "hub2hub.cli.main:app"

[dependency-groups]
dev = [
    "hypothesis>=6.100",
    "mypy>=1.10",
    "pytest>=8.2",
    "pytest-cov>=5.0",
    "respx>=0.21",
    "ruff>=0.5",
    "syrupy>=4.6",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["hub2hub"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "S", "RUF"]
ignore = ["S101"]  # assert OK dans tests

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S"]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["hub2hub"]

[[tool.mypy.overrides]]
module = ["hub2hub.adapters.*", "hub2hub.cli.*"]
disallow_untyped_calls = false  # plus laxiste sur les couches I/O

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"

[tool.coverage.run]
branch = true
source = ["hub2hub"]
omit = ["hub2hub/cli/_di.py"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

- [ ] **Step 3 : Mettre à jour `.gitignore`**

Modifier `.gitignore` pour ajouter (en plus de ce qui existe) :

```
__pycache__/
*.pyc
.venv/
.uv-cache/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
coverage.xml
htmlcov/
dist/
*.egg-info/
```

- [ ] **Step 4 : Créer les fichiers `__init__.py` vides**

```bash
mkdir -p hub2hub tests
touch hub2hub/__init__.py tests/__init__.py tests/conftest.py
```

- [ ] **Step 5 : Bootstrap uv et venv**

```bash
uv sync
```

Expected : crée `.venv/` et `uv.lock`. Commande termine sans erreur.

- [ ] **Step 6 : Smoke test pytest**

```bash
uv run pytest
```

Expected : `no tests ran` (collection vide), exit 5.

- [ ] **Step 7 : Smoke test ruff**

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected : both pass (rien à signaler).

- [ ] **Step 8 : Commit**

```bash
git add pyproject.toml uv.lock .python-version .gitignore hub2hub/ tests/
git commit -m "feat(python): initialise le projet uv + ruff + mypy + pytest"
```

---

### Task 2 : `hub2hub/errors.py` — hiérarchie d'exceptions et exit codes

**Files:**
- Create: `hub2hub/errors.py`
- Create: `tests/unit/test_errors.py`

Référence spec §6.3.

- [ ] **Step 1 : Écrire le test**

`tests/unit/test_errors.py` :

```python
import pytest

from hub2hub.errors import (
    AdapterError,
    ConfigError,
    DomainError,
    H2HError,
    HarborAuthError,
    HarborError,
    HarborNotFoundError,
    HarborTransientError,
    InternalError,
    NoTagsToImportError,
    PropertiesValidationError,
    exit_code_for,
)


def test_hierarchy() -> None:
    assert issubclass(DomainError, H2HError)
    assert issubclass(AdapterError, H2HError)
    assert issubclass(ConfigError, H2HError)
    assert issubclass(InternalError, H2HError)
    assert issubclass(HarborError, AdapterError)
    assert issubclass(HarborAuthError, HarborError)
    assert issubclass(HarborNotFoundError, HarborError)
    assert issubclass(HarborTransientError, HarborError)
    assert issubclass(PropertiesValidationError, DomainError)
    assert issubclass(NoTagsToImportError, DomainError)


@pytest.mark.parametrize(
    "exc,expected_code",
    [
        (DomainError("x"), 1),
        (PropertiesValidationError("x"), 1),
        (AdapterError("x"), 2),
        (HarborAuthError("x"), 2),
        (ConfigError("x"), 3),
        (InternalError("x"), 4),
    ],
)
def test_exit_codes(exc: H2HError, expected_code: int) -> None:
    assert exit_code_for(exc) == expected_code


def test_exit_code_for_unknown_exception() -> None:
    assert exit_code_for(RuntimeError("boom")) == 4
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

```bash
uv run pytest tests/unit/test_errors.py -v
```

Expected : `ImportError: cannot import name 'H2HError' from 'hub2hub.errors'`.

- [ ] **Step 3 : Implémenter `hub2hub/errors.py`**

```python
"""Hiérarchie d'exceptions et table des exit codes du CLI h2h.

Voir spec §6.3.
"""

from __future__ import annotations


class H2HError(Exception):
    """Racine de toutes les erreurs métier/infra du CLI."""


class DomainError(H2HError):
    """Erreur métier ou de validation (exit 1)."""


class PropertiesValidationError(DomainError):
    pass


class NoTagsToImportError(DomainError):
    pass


class EolDateInconsistencyError(DomainError):
    pass


class AdapterError(H2HError):
    """Erreur infrastructure / dépendance externe (exit 2)."""


class HarborError(AdapterError):
    pass


class HarborAuthError(HarborError):
    pass


class HarborNotFoundError(HarborError):
    pass


class HarborTransientError(HarborError):
    pass


class GitError(AdapterError):
    pass


class SkopeoError(AdapterError):
    pass


class BuildkitError(AdapterError):
    pass


class GitLabError(AdapterError):
    pass


class EolSourceError(AdapterError):
    pass


class ConfigError(H2HError):
    """Configuration invalide / manquante (exit 3)."""


class InternalError(H2HError):
    """Bug, assertion, condition inattendue (exit 4)."""


_EXIT_CODES: dict[type[H2HError], int] = {
    DomainError: 1,
    AdapterError: 2,
    ConfigError: 3,
    InternalError: 4,
}


def exit_code_for(exc: BaseException) -> int:
    """Retourne l'exit code pour une exception.

    Toute exception inconnue est traitée comme une InternalError (exit 4).
    """
    for base, code in _EXIT_CODES.items():
        if isinstance(exc, base):
            return code
    return 4
```

- [ ] **Step 4 : Lancer le test, vérifier qu'il passe**

```bash
uv run pytest tests/unit/test_errors.py -v
```

Expected : 8 tests pass.

- [ ] **Step 5 : Commit**

```bash
git add hub2hub/errors.py tests/unit/test_errors.py
git commit -m "feat(python): ajoute hiérarchie d'exceptions H2HError et exit codes"
```

---

### Task 3 : `hub2hub/config.py` — Pydantic Settings

**Files:**
- Create: `hub2hub/config.py`
- Create: `tests/unit/test_config.py`

Référence spec §6.1.

- [ ] **Step 1 : Écrire le test**

`tests/unit/test_config.py` :

```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from hub2hub.config import HarborSettings, Settings


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("H2H_HARBOR_URL", "https://harbor.example.com")
    monkeypatch.setenv("H2H_HARBOR_USER", "robot$h2h")
    monkeypatch.setenv("H2H_HARBOR_PASSWORD", "s3cret")
    monkeypatch.setenv("H2H_GITLAB_URL", "https://gitlab.example.com")
    monkeypatch.setenv("H2H_GITLAB_TOKEN", "glpat-xxx")
    monkeypatch.setenv("H2H_GITLAB_GROUP", "eul/h2h/products")
    monkeypatch.setenv("H2H_WORK_DIR", str(tmp_path))

    settings = Settings()

    assert settings.harbor.url == "https://harbor.example.com"
    assert settings.harbor.password.get_secret_value() == "s3cret"
    assert settings.gitlab.token.get_secret_value() == "glpat-xxx"
    assert settings.work_dir == tmp_path
    assert settings.log_format == "text"  # défaut
    assert settings.log_level == "INFO"   # défaut


def test_settings_secrets_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("H2H_HARBOR_URL", "https://h")
    monkeypatch.setenv("H2H_HARBOR_USER", "u")
    monkeypatch.setenv("H2H_HARBOR_PASSWORD", "s3cret-leak")
    monkeypatch.setenv("H2H_GITLAB_URL", "https://g")
    monkeypatch.setenv("H2H_GITLAB_TOKEN", "tok-leak")
    monkeypatch.setenv("H2H_GITLAB_GROUP", "g")

    settings = Settings()
    text = repr(settings)
    assert "s3cret-leak" not in text
    assert "tok-leak" not in text


def test_settings_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("H2H_HARBOR_URL", "H2H_HARBOR_USER", "H2H_HARBOR_PASSWORD",
                 "H2H_GITLAB_URL", "H2H_GITLAB_TOKEN", "H2H_GITLAB_GROUP"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_teams_webhook_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("H2H_HARBOR_URL", "https://h")
    monkeypatch.setenv("H2H_HARBOR_USER", "u")
    monkeypatch.setenv("H2H_HARBOR_PASSWORD", "s")
    monkeypatch.setenv("H2H_GITLAB_URL", "https://g")
    monkeypatch.setenv("H2H_GITLAB_TOKEN", "t")
    monkeypatch.setenv("H2H_GITLAB_GROUP", "grp")
    monkeypatch.delenv("H2H_TEAMS_WEBHOOK_URL", raising=False)

    settings = Settings()
    assert settings.teams_webhook_url is None


def test_harbor_settings_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les sous-blocs Settings doivent supporter une instanciation directe pour les tests."""
    h = HarborSettings(url="https://x", user="u", password="p")
    assert h.password.get_secret_value() == "p"


def test_invalid_log_level_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une valeur de `H2H_LOG_LEVEL` hors du Literal doit lever ValidationError."""
    monkeypatch.setenv("H2H_HARBOR_URL", "https://h")
    monkeypatch.setenv("H2H_HARBOR_USER", "u")
    monkeypatch.setenv("H2H_HARBOR_PASSWORD", "p")
    monkeypatch.setenv("H2H_GITLAB_URL", "https://g")
    monkeypatch.setenv("H2H_GITLAB_TOKEN", "t")
    monkeypatch.setenv("H2H_GITLAB_GROUP", "g")
    monkeypatch.setenv("H2H_LOG_LEVEL", "TRACE")

    with pytest.raises(ValidationError):
        Settings()


def test_endoflife_url_validated_but_str(monkeypatch: pytest.MonkeyPatch) -> None:
    """`endoflife_url` est validé comme URL mais exposé comme `str` pour httpx."""
    monkeypatch.setenv("H2H_HARBOR_URL", "https://h")
    monkeypatch.setenv("H2H_HARBOR_USER", "u")
    monkeypatch.setenv("H2H_HARBOR_PASSWORD", "p")
    monkeypatch.setenv("H2H_GITLAB_URL", "https://g")
    monkeypatch.setenv("H2H_GITLAB_TOKEN", "t")
    monkeypatch.setenv("H2H_GITLAB_GROUP", "g")
    monkeypatch.setenv("H2H_ENDOFLIFE_URL", "https://eol.test/api")

    settings = Settings()
    assert isinstance(settings.endoflife_url, str)
    assert settings.endoflife_url == "https://eol.test/api"

    monkeypatch.setenv("H2H_ENDOFLIFE_URL", "not-a-url")
    with pytest.raises(ValidationError):
        Settings()
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected : ImportError sur `hub2hub.config`.

- [ ] **Step 3 : Implémenter `hub2hub/config.py`**

> **Note architecturale** : le contrat env du spec §6.1 utilise un seul underscore (`H2H_HARBOR_URL`). Pour préserver ce contrat *et* l'API ergonomique `settings.harbor.url`, chaque sous-bloc est un `BaseSettings` avec son propre `env_prefix`. La racine les compose via `default_factory`. Une première version utilisait `BaseModel` + `env_nested_delimiter="__"` (qui exigerait `H2H_HARBOR__URL`) et a été abandonnée car incompatible avec le spec et avec les tests ci-dessus.

```python
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


def _build_harbor() -> HarborSettings:
    return HarborSettings.model_validate({})


def _build_harbor_orange() -> HarborOrangeSettings:
    return HarborOrangeSettings.model_validate({})


def _build_gitlab() -> GitLabSettings:
    return GitLabSettings.model_validate({})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="H2H_",
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
```

- [ ] **Step 4 : Lancer le test**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected : 7 tests pass.

- [ ] **Step 5 : Commit**

```bash
git add hub2hub/config.py tests/unit/test_config.py
git commit -m "feat(python): ajoute Settings Pydantic (lecture env vars H2H_*)"
```

---

### Task 4 : `hub2hub/logging.py` — setup structlog

**Files:**
- Create: `hub2hub/logging.py`
- Create: `tests/unit/test_logging.py`

- [ ] **Step 1 : Écrire le test**

`tests/unit/test_logging.py` :

```python
import json
import logging
from io import StringIO

import structlog

from hub2hub.logging import configure


def test_text_format_produces_human_readable() -> None:
    buf = StringIO()
    configure(format_="text", level="INFO", stream=buf)

    log = structlog.get_logger("test")
    log.info("hello", project="p1", tag="v1")

    out = buf.getvalue()
    assert "hello" in out
    assert "project=p1" in out
    assert "tag=v1" in out


def test_json_format_produces_one_object_per_line() -> None:
    buf = StringIO()
    configure(format_="json", level="INFO", stream=buf)

    log = structlog.get_logger("test")
    log.info("hello", project="p1", tag="v1")

    line = buf.getvalue().strip()
    obj = json.loads(line)
    assert obj["event"] == "hello"
    assert obj["project"] == "p1"
    assert obj["tag"] == "v1"
    assert obj["level"] == "info"


def test_level_filters_debug() -> None:
    buf = StringIO()
    configure(format_="text", level="INFO", stream=buf)

    log = structlog.get_logger("test")
    log.debug("noisy")

    assert buf.getvalue() == ""


def test_warn_alias_for_warning() -> None:
    buf = StringIO()
    configure(format_="json", level="WARN", stream=buf)

    log = structlog.get_logger("test")
    log.info("filtered")
    log.warning("kept")

    lines = [line for line in buf.getvalue().splitlines() if line]
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "kept"


def teardown_module() -> None:  # restore root logger config
    logging.getLogger().handlers.clear()
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

```bash
uv run pytest tests/unit/test_logging.py -v
```

Expected : ImportError.

- [ ] **Step 3 : Implémenter `hub2hub/logging.py`**

```python
"""Configuration de structlog pour le CLI h2h.

Voir spec §6.3 — logs structurés JSON/text.
"""

from __future__ import annotations

import logging
import sys
from typing import IO, Literal

import structlog


def _level_to_int(level: str) -> int:
    normalized = "WARNING" if level == "WARN" else level
    return getattr(logging, normalized)


def configure(
    *,
    format_: Literal["text", "json"] = "text",
    level: str = "INFO",
    stream: IO[str] | None = None,
) -> None:
    """(Re)configure structlog et logging stdlib.

    `stream` permet de rediriger vers un buffer dans les tests.
    """
    stream = stream if stream is not None else sys.stderr

    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(_level_to_int(level))

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if format_ == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(_level_to_int(level)),
        logger_factory=structlog.PrintLoggerFactory(stream),
        cache_logger_on_first_use=False,
    )
```

- [ ] **Step 4 : Lancer le test**

```bash
uv run pytest tests/unit/test_logging.py -v
```

Expected : 4 tests pass.

- [ ] **Step 5 : Commit**

```bash
git add hub2hub/logging.py tests/unit/test_logging.py
git commit -m "feat(python): ajoute configuration structlog (text|json)"
```

---

## Groupe 2 — Ports

### Task 5 : `hub2hub/ports/clock.py` + `domain` helpers

**Files:**
- Create: `hub2hub/ports/__init__.py`
- Create: `hub2hub/ports/clock.py`
- Create: `tests/fakes/__init__.py`
- Create: `tests/fakes/clock.py`

- [ ] **Step 1 : Écrire le test du fake**

`tests/unit/test_fakes_clock.py` :

```python
from datetime import UTC, datetime, timedelta

from tests.fakes.clock import FakeClock


def test_fake_clock_returns_set_value() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FakeClock(now)
    assert clock.now() == now


def test_fake_clock_advance() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FakeClock(now)
    clock.advance(timedelta(days=2))
    assert clock.now() == datetime(2026, 1, 3, tzinfo=UTC)
```

- [ ] **Step 2 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/unit/test_fakes_clock.py -v
```

Expected : ImportError.

- [ ] **Step 3 : Implémenter le port et le fake**

`hub2hub/ports/__init__.py` :

```python
```

`hub2hub/ports/clock.py` :

```python
"""Port d'accès au temps. Permet de figer `now()` dans les tests."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> datetime: ...
```

`tests/fakes/__init__.py` :

```python
```

`tests/fakes/clock.py` :

```python
from __future__ import annotations

from datetime import datetime, timedelta


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta
```

- [ ] **Step 4 : Lancer le test**

```bash
uv run pytest tests/unit/test_fakes_clock.py -v
```

Expected : 2 tests pass.

- [ ] **Step 5 : Commit**

```bash
git add hub2hub/ports/ tests/fakes/ tests/unit/test_fakes_clock.py
git commit -m "feat(python): ajoute ClockPort et FakeClock"
```

---

### Task 6 : `hub2hub/ports/harbor.py` (read-only) + `FakeHarbor`

**Files:**
- Create: `hub2hub/ports/harbor.py`
- Create: `tests/fakes/harbor.py`

Note : seuls les méthodes en lecture utiles à `h2h dev capture` et à `domain/tag_filter` sont définies en Phase A. Les méthodes d'écriture (POST/DELETE) seront ajoutées en Phase B.

- [ ] **Step 1 : Écrire le test du fake**

`tests/unit/test_fakes_harbor.py` :

```python
from hub2hub.ports.harbor import Artifact, Repository
from tests.fakes.harbor import FakeHarborPort


def test_get_repositories_returns_seeded() -> None:
    repos = [Repository(name="rancher/k3s", project_id=1)]
    harbor = FakeHarborPort(repositories={"04228.proxy.docker.io": repos})

    assert harbor.get_repositories("04228.proxy.docker.io") == repos


def test_get_artifacts_returns_seeded() -> None:
    arts = [Artifact(digest="sha256:abc", tags=["v1.0.0"], push_time="2026-01-01T00:00:00Z")]
    harbor = FakeHarborPort(artifacts={("04228.proxy.docker.io", "rancher/k3s"): arts})

    assert harbor.get_artifacts("04228.proxy.docker.io", "rancher/k3s") == arts


def test_get_artifacts_unknown_returns_empty() -> None:
    harbor = FakeHarborPort()
    assert harbor.get_artifacts("p", "r") == []
```

- [ ] **Step 2 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/unit/test_fakes_harbor.py -v
```

Expected : ImportError.

- [ ] **Step 3 : Implémenter le port**

`hub2hub/ports/harbor.py` :

```python
"""Port d'accès à Harbor v2 (lectures uniquement en Phase A).

Voir spec §4. Les méthodes d'écriture (copy_artifact, delete_artifact_tag,
add_artifact_tag, update_immutabletagrule) seront ajoutées en Phase B.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Repository:
    name: str
    project_id: int
    artifact_count: int = 0


@dataclass(frozen=True)
class Artifact:
    digest: str
    tags: list[str] = field(default_factory=list)
    push_time: str = ""
    labels: list[str] = field(default_factory=list)


class HarborPort(Protocol):
    def get_repositories(self, project_name: str) -> list[Repository]: ...
    def get_artifacts(self, project_name: str, repository_name: str) -> list[Artifact]: ...
```

`tests/fakes/harbor.py` :

```python
from __future__ import annotations

from hub2hub.ports.harbor import Artifact, Repository


class FakeHarborPort:
    def __init__(
        self,
        repositories: dict[str, list[Repository]] | None = None,
        artifacts: dict[tuple[str, str], list[Artifact]] | None = None,
    ) -> None:
        self._repositories = repositories or {}
        self._artifacts = artifacts or {}

    def get_repositories(self, project_name: str) -> list[Repository]:
        return list(self._repositories.get(project_name, []))

    def get_artifacts(self, project_name: str, repository_name: str) -> list[Artifact]:
        return list(self._artifacts.get((project_name, repository_name), []))
```

- [ ] **Step 4 : Lancer le test**

```bash
uv run pytest tests/unit/test_fakes_harbor.py -v
```

Expected : 3 tests pass.

- [ ] **Step 5 : Commit**

```bash
git add hub2hub/ports/harbor.py tests/fakes/harbor.py tests/unit/test_fakes_harbor.py
git commit -m "feat(python): ajoute HarborPort (read-only) et FakeHarborPort"
```

---

### Task 7 : `hub2hub/ports/source_registry.py` + `FakeSourceRegistry`

**Files:**
- Create: `hub2hub/ports/source_registry.py`
- Create: `tests/fakes/source_registry.py`

Wrapper Python autour de `skopeo inspect` et `skopeo list-tags`.

- [ ] **Step 1 : Écrire le test du fake**

`tests/unit/test_fakes_source_registry.py` :

```python
from hub2hub.ports.source_registry import SourceImage
from tests.fakes.source_registry import FakeSourceRegistryPort


def test_list_tags() -> None:
    src = FakeSourceRegistryPort(tags={"docker.io/rancher/k3s": ["v1.28.5", "v1.29.0"]})
    assert src.list_tags("docker.io/rancher/k3s") == ["v1.28.5", "v1.29.0"]


def test_inspect_returns_image() -> None:
    image = SourceImage(digest="sha256:abc", architecture="amd64", os="linux")
    src = FakeSourceRegistryPort(images={"docker.io/rancher/k3s:v1.29.0": image})
    assert src.inspect("docker.io/rancher/k3s:v1.29.0") == image
```

- [ ] **Step 2 : Lancer**

```bash
uv run pytest tests/unit/test_fakes_source_registry.py -v
```

Expected : ImportError.

- [ ] **Step 3 : Implémenter le port**

`hub2hub/ports/source_registry.py` :

```python
"""Port d'accès aux registres sources (lectures via skopeo)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SourceImage:
    digest: str
    architecture: str
    os: str


class SourceRegistryPort(Protocol):
    def list_tags(self, image_ref: str) -> list[str]: ...
    def inspect(self, image_ref: str) -> SourceImage: ...
```

`tests/fakes/source_registry.py` :

```python
from __future__ import annotations

from hub2hub.ports.source_registry import SourceImage


class FakeSourceRegistryPort:
    def __init__(
        self,
        tags: dict[str, list[str]] | None = None,
        images: dict[str, SourceImage] | None = None,
    ) -> None:
        self._tags = tags or {}
        self._images = images or {}

    def list_tags(self, image_ref: str) -> list[str]:
        return list(self._tags.get(image_ref, []))

    def inspect(self, image_ref: str) -> SourceImage:
        return self._images[image_ref]
```

- [ ] **Step 4 : Lancer**

```bash
uv run pytest tests/unit/test_fakes_source_registry.py -v
```

Expected : 2 tests pass.

- [ ] **Step 5 : Commit**

```bash
git add hub2hub/ports/source_registry.py tests/fakes/source_registry.py tests/unit/test_fakes_source_registry.py
git commit -m "feat(python): ajoute SourceRegistryPort et fake"
```

---

## Groupe 3 — Adaptateurs read-only

### Task 8 : `hub2hub/adapters/system_clock.py`

**Files:**
- Create: `hub2hub/adapters/__init__.py`
- Create: `hub2hub/adapters/system_clock.py`
- Create: `tests/unit/test_system_clock.py`

- [ ] **Step 1 : Écrire le test**

`tests/unit/test_system_clock.py` :

```python
from datetime import UTC, datetime, timedelta

from hub2hub.adapters.system_clock import SystemClock


def test_now_returns_utc_datetime_close_to_real_time() -> None:
    before = datetime.now(UTC)
    got = SystemClock().now()
    after = datetime.now(UTC)

    assert before - timedelta(seconds=1) <= got <= after + timedelta(seconds=1)
    assert got.tzinfo is not None
```

- [ ] **Step 2 : Lancer**

```bash
uv run pytest tests/unit/test_system_clock.py -v
```

Expected : ImportError.

- [ ] **Step 3 : Implémenter**

`hub2hub/adapters/__init__.py` :

```python
```

`hub2hub/adapters/system_clock.py` :

```python
from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
```

- [ ] **Step 4 : Lancer**

```bash
uv run pytest tests/unit/test_system_clock.py -v
```

Expected : pass.

- [ ] **Step 5 : Commit**

```bash
git add hub2hub/adapters/ tests/unit/test_system_clock.py
git commit -m "feat(python): ajoute SystemClock (datetime.now UTC)"
```

---

### Task 9 : `hub2hub/adapters/harbor_http.py` — méthodes en lecture

**Files:**
- Create: `hub2hub/adapters/harbor_http.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_harbor_http.py`

Inspiré de `ci/harbor.py` (existant) mais en réécriture stricte autour de `httpx` + `tenacity`. Référence : `vars/HarborApi.groovy` pour les retries et la pagination.

- [ ] **Step 1 : Écrire les tests d'intégration (HTTP mocké via respx)**

`tests/integration/__init__.py` :

```python
```

`tests/integration/test_harbor_http.py` :

```python
import httpx
import pytest
import respx

from hub2hub.adapters.harbor_http import HarborHttpAdapter
from hub2hub.errors import HarborAuthError, HarborNotFoundError, HarborTransientError


@pytest.fixture()
def adapter() -> HarborHttpAdapter:
    return HarborHttpAdapter(
        base_url="https://harbor.example.com",
        user="robot$h2h",
        password="s3cret",
    )


def test_get_repositories_paginates_until_empty(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        page1 = [{"name": "lib/a", "project_id": 1, "artifact_count": 2}]
        page2 = [{"name": "lib/b", "project_id": 1, "artifact_count": 1}]
        router.get("/api/v2.0/projects/lib/repositories", params={"page": "1", "page_size": "100"}).respond(200, json=page1)
        router.get("/api/v2.0/projects/lib/repositories", params={"page": "2", "page_size": "100"}).respond(200, json=page2)
        router.get("/api/v2.0/projects/lib/repositories", params={"page": "3", "page_size": "100"}).respond(200, json=[])

        repos = adapter.get_repositories("lib")
        assert [r.name for r in repos] == ["lib/a", "lib/b"]


def test_get_artifacts_url_double_encodes_repository(adapter: HarborHttpAdapter) -> None:
    """Bug historique : un repo `foo/bar` doit être double-encodé dans l'URL."""
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.get("/api/v2.0/projects/lib/repositories/foo%252Fbar/artifacts").respond(200, json=[])
        adapter.get_artifacts("lib", "foo/bar")
        assert route.called


def test_auth_error_maps_401(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get("/api/v2.0/projects/lib/repositories").respond(401, json={"errors": []})
        with pytest.raises(HarborAuthError):
            adapter.get_repositories("lib")


def test_not_found_error_maps_404(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get("/api/v2.0/projects/lib/repositories").respond(404, json={"errors": []})
        with pytest.raises(HarborNotFoundError):
            adapter.get_repositories("lib")


def test_transient_5xx_retried_then_succeeds(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        responses = [
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json=[]),
        ]
        route = router.get("/api/v2.0/projects/lib/repositories", params={"page": "1", "page_size": "100"}).mock(side_effect=responses)
        adapter.get_repositories("lib")
        assert route.call_count == 3


def test_transient_5xx_exhausts_retries_then_raises(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get("/api/v2.0/projects/lib/repositories", params={"page": "1", "page_size": "100"}).respond(503)
        with pytest.raises(HarborTransientError):
            adapter.get_repositories("lib")
```

- [ ] **Step 2 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/integration/test_harbor_http.py -v
```

Expected : ImportError.

- [ ] **Step 3 : Implémenter `hub2hub/adapters/harbor_http.py`**

```python
"""Adaptateur HTTP pour Harbor v2 (méthodes de lecture)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import quote

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from hub2hub.errors import (
    HarborAuthError,
    HarborError,
    HarborNotFoundError,
    HarborTransientError,
)
from hub2hub.ports.harbor import Artifact, Repository

PAGE_SIZE = 100
MAX_ATTEMPTS = 5


class HarborHttpAdapter:
    def __init__(self, *, base_url: str, user: str, password: str) -> None:
        self._base = base_url.rstrip("/") + "/api/v2.0"
        self._client = httpx.Client(
            auth=(user, password),
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Accept": "application/json"},
        )

    def get_repositories(self, project_name: str) -> list[Repository]:
        items = list(self._paginate(f"/projects/{project_name}/repositories"))
        return [
            Repository(
                name=item["name"],
                project_id=item["project_id"],
                artifact_count=item.get("artifact_count", 0),
            )
            for item in items
        ]

    def get_artifacts(self, project_name: str, repository_name: str) -> list[Artifact]:
        repo_encoded = quote(quote(repository_name, safe=""), safe="")
        path = f"/projects/{project_name}/repositories/{repo_encoded}/artifacts"
        items = list(self._paginate(path))
        return [
            Artifact(
                digest=item["digest"],
                tags=[t["name"] for t in (item.get("tags") or [])],
                push_time=item.get("push_time", ""),
                labels=[lab["name"] for lab in (item.get("labels") or [])],
            )
            for item in items
        ]

    def _paginate(self, path: str) -> Iterable[dict[str, Any]]:
        page = 1
        while True:
            data = self._get(path, params={"page": page, "page_size": PAGE_SIZE})
            if not data:
                return
            yield from data
            page += 1

    @retry(
        retry=retry_if_exception_type(HarborTransientError),
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, max=2.0),
        reraise=True,
    )
    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        try:
            r = self._client.get(self._base + path, params=params)
        except httpx.HTTPError as e:
            raise HarborTransientError(str(e)) from e

        if r.status_code == 401:
            raise HarborAuthError(r.text)
        if r.status_code == 404:
            raise HarborNotFoundError(f"{path}: {r.text}")
        if 500 <= r.status_code < 600:
            raise HarborTransientError(f"{r.status_code}: {r.text}")
        if not r.is_success:
            raise HarborError(f"{r.status_code}: {r.text}")
        return r.json()
```

- [ ] **Step 4 : Lancer les tests**

```bash
uv run pytest tests/integration/test_harbor_http.py -v
```

Expected : 6 tests pass.

- [ ] **Step 5 : Commit**

```bash
git add hub2hub/adapters/harbor_http.py tests/integration/test_harbor_http.py tests/integration/__init__.py
git commit -m "feat(python): ajoute HarborHttpAdapter (read-only) avec retries et pagination"
```

---

### Task 10 : `hub2hub/adapters/skopeo_cli.py` — wrapper subprocess

**Files:**
- Create: `hub2hub/adapters/skopeo_cli.py`
- Create: `tests/fake-bins/skopeo` (script shell mock)
- Create: `tests/integration/test_skopeo_cli.py`
- Modify: `tests/conftest.py` (fixture `fake_bin_path`)

- [ ] **Step 1 : Écrire la fixture conftest**

`tests/conftest.py` (remplacement complet) :

```python
"""Fixtures globales pour les tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture()
def fake_bin_path(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Place tests/fake-bins/ en tête de PATH pour ce test."""
    here = Path(__file__).parent / "fake-bins"
    monkeypatch.setenv("PATH", f"{here}{os.pathsep}{os.environ['PATH']}")
    yield here
```

- [ ] **Step 2 : Écrire le binaire mock**

`tests/fake-bins/skopeo` (exécutable) :

```bash
#!/usr/bin/env sh
# Fake skopeo pour tests d'intégration.
# Récupère le scénario via la variable d'env FAKE_SKOPEO_SCENARIO.

set -e

case "${FAKE_SKOPEO_SCENARIO:-default}" in
    inspect-busybox)
        cat <<'JSON'
{
  "Digest": "sha256:abc123",
  "Architecture": "amd64",
  "Os": "linux"
}
JSON
        ;;
    list-tags-busybox)
        cat <<'JSON'
{"Repository": "docker.io/library/busybox", "Tags": ["1.36", "1.37", "latest"]}
JSON
        ;;
    fail)
        echo "skopeo: simulated failure" >&2
        exit 1
        ;;
    *)
        echo "fake-skopeo: unknown scenario ${FAKE_SKOPEO_SCENARIO}" >&2
        exit 99
        ;;
esac
```

Le rendre exécutable :

```bash
chmod +x tests/fake-bins/skopeo
```

- [ ] **Step 3 : Écrire les tests**

`tests/integration/test_skopeo_cli.py` :

```python
from pathlib import Path

import pytest

from hub2hub.adapters.skopeo_cli import SkopeoAdapter
from hub2hub.errors import SkopeoError


def test_list_tags(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_SKOPEO_SCENARIO", "list-tags-busybox")
    tags = SkopeoAdapter().list_tags("docker.io/library/busybox")
    assert tags == ["1.36", "1.37", "latest"]


def test_inspect(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_SKOPEO_SCENARIO", "inspect-busybox")
    img = SkopeoAdapter().inspect("docker.io/library/busybox:1.36")
    assert img.digest == "sha256:abc123"
    assert img.architecture == "amd64"
    assert img.os == "linux"


def test_failure_raises_skopeo_error(fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_SKOPEO_SCENARIO", "fail")
    with pytest.raises(SkopeoError):
        SkopeoAdapter().inspect("docker.io/library/busybox:1.36")
```

- [ ] **Step 4 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/integration/test_skopeo_cli.py -v
```

Expected : ImportError.

- [ ] **Step 5 : Implémenter `hub2hub/adapters/skopeo_cli.py`**

```python
"""Wrapper subprocess autour de skopeo (lectures uniquement)."""

from __future__ import annotations

import json
import shutil
import subprocess

from hub2hub.errors import SkopeoError
from hub2hub.ports.source_registry import SourceImage


class SkopeoAdapter:
    def __init__(self, binary: str | None = None) -> None:
        resolved = binary or shutil.which("skopeo")
        if not resolved:
            raise SkopeoError("skopeo binary not found in PATH")
        self._bin = resolved

    def list_tags(self, image_ref: str) -> list[str]:
        out = self._run(["list-tags", f"docker://{image_ref}"])
        try:
            payload = json.loads(out)
        except json.JSONDecodeError as e:
            raise SkopeoError(f"invalid JSON from skopeo list-tags: {e}") from e
        return list(payload.get("Tags", []))

    def inspect(self, image_ref: str) -> SourceImage:
        out = self._run(["inspect", f"docker://{image_ref}"])
        try:
            payload = json.loads(out)
        except json.JSONDecodeError as e:
            raise SkopeoError(f"invalid JSON from skopeo inspect: {e}") from e
        return SourceImage(
            digest=payload["Digest"],
            architecture=payload.get("Architecture", ""),
            os=payload.get("Os", ""),
        )

    def _run(self, args: list[str]) -> str:
        try:
            r = subprocess.run(  # noqa: S603
                [self._bin, *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise SkopeoError(str(e)) from e
        if r.returncode != 0:
            raise SkopeoError(f"skopeo {' '.join(args)} failed: {r.stderr.strip()}")
        return r.stdout
```

- [ ] **Step 6 : Lancer les tests**

```bash
uv run pytest tests/integration/test_skopeo_cli.py -v
```

Expected : 3 tests pass.

- [ ] **Step 7 : Commit**

```bash
git add hub2hub/adapters/skopeo_cli.py tests/fake-bins/skopeo tests/integration/test_skopeo_cli.py tests/conftest.py
git commit -m "feat(python): ajoute SkopeoAdapter (inspect + list-tags) avec fake-bin"
```

---

## Groupe 4 — CLI scaffolding + `h2h dev capture`

### Task 11 : `hub2hub/cli/main.py` + `h2h version`

**Files:**
- Create: `hub2hub/cli/__init__.py`
- Create: `hub2hub/cli/main.py`
- Create: `hub2hub/cli/_di.py`
- Create: `tests/integration/test_cli_main.py`

- [ ] **Step 1 : Écrire le test**

`tests/integration/test_cli_main.py` :

```python
from typer.testing import CliRunner

from hub2hub.cli.main import app


def test_h2h_version_outputs_version_string() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_h2h_help_lists_subgroups() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "dev" in result.stdout
    assert "version" in result.stdout
```

- [ ] **Step 2 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/integration/test_cli_main.py -v
```

Expected : ImportError.

- [ ] **Step 3 : Implémenter le squelette CLI**

`hub2hub/cli/__init__.py` :

```python
```

`hub2hub/cli/_di.py` :

```python
"""Composition root. Construit les adapters concrets à partir des Settings.

Volontairement non couvert par les tests unitaires (cf. coverage omit).
"""

from __future__ import annotations

from dataclasses import dataclass

from hub2hub.adapters.harbor_http import HarborHttpAdapter
from hub2hub.adapters.skopeo_cli import SkopeoAdapter
from hub2hub.adapters.system_clock import SystemClock
from hub2hub.config import Settings


@dataclass(frozen=True)
class Container:
    settings: Settings
    harbor: HarborHttpAdapter
    skopeo: SkopeoAdapter
    clock: SystemClock


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()  # type: ignore[call-arg]
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
```

`hub2hub/cli/main.py` :

```python
"""Point d'entrée Typer de la CLI h2h.

Voir spec §3.
"""

from __future__ import annotations

import importlib.metadata

import typer

from hub2hub.cli import dev as dev_cli

app = typer.Typer(name="h2h", no_args_is_help=True, add_completion=False)
app.add_typer(dev_cli.app, name="dev", help="Outils de développement (capture de fixtures, debug)")


@app.command()
def version() -> None:
    """Affiche la version du CLI."""
    try:
        v = importlib.metadata.version("hub2hub")
    except importlib.metadata.PackageNotFoundError:
        v = "0.1.0-dev"
    typer.echo(v)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4 : Stub `hub2hub/cli/dev.py` minimal** (sera étoffé en Task 12)

```python
from __future__ import annotations

import typer

app = typer.Typer(name="dev", help="Outils de développement (capture de fixtures, debug)")


@app.callback()
def _root() -> None:
    """Sous-groupe de commandes internes."""
```

- [ ] **Step 5 : Lancer les tests**

```bash
uv run pytest tests/integration/test_cli_main.py -v
```

Expected : 2 tests pass.

- [ ] **Step 6 : Smoke test CLI**

```bash
uv run h2h version
uv run h2h --help
```

Expected : la version s'affiche, l'aide liste `dev` et `version`.

- [ ] **Step 7 : Commit**

```bash
git add hub2hub/cli/ tests/integration/test_cli_main.py
git commit -m "feat(python): ajoute squelette CLI Typer (h2h version + sous-groupe dev)"
```

---

### Task 12 : `h2h dev capture` — capture de fixtures depuis Harbor

**Files:**
- Modify: `hub2hub/cli/dev.py`
- Create: `tests/integration/test_cli_dev_capture.py`

But : `h2h dev capture --project P --repository R --output DIR` lit l'état Harbor d'un repo (repository + artifacts) et écrit un JSON par appel API sous `DIR/`. Sert à constituer les fixtures de `tests/fixtures/captured/`.

- [ ] **Step 1 : Écrire le test**

`tests/integration/test_cli_dev_capture.py` :

```python
import json
from pathlib import Path

import pytest
import respx
from typer.testing import CliRunner

from hub2hub.cli.main import app


@pytest.fixture()
def harbor_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("H2H_HARBOR_URL", "https://harbor.example.com")
    monkeypatch.setenv("H2H_HARBOR_USER", "u")
    monkeypatch.setenv("H2H_HARBOR_PASSWORD", "p")
    monkeypatch.setenv("H2H_GITLAB_URL", "https://gl")
    monkeypatch.setenv("H2H_GITLAB_TOKEN", "t")
    monkeypatch.setenv("H2H_GITLAB_GROUP", "g")


def test_capture_writes_repositories_and_artifacts(
    harbor_env: None,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get("/api/v2.0/projects/lib/repositories", params={"page": "1", "page_size": "100"}).respond(
            200,
            json=[{"name": "lib/foo", "project_id": 1, "artifact_count": 1}],
        )
        router.get("/api/v2.0/projects/lib/repositories", params={"page": "2", "page_size": "100"}).respond(
            200, json=[]
        )
        router.get("/api/v2.0/projects/lib/repositories/foo/artifacts", params={"page": "1", "page_size": "100"}).respond(
            200,
            json=[{"digest": "sha256:abc", "tags": [{"name": "v1"}], "push_time": "2026-01-01T00:00:00Z"}],
        )
        router.get("/api/v2.0/projects/lib/repositories/foo/artifacts", params={"page": "2", "page_size": "100"}).respond(
            200, json=[]
        )

        result = runner.invoke(
            app,
            ["dev", "capture", "--project", "lib", "--repository", "foo", "--output", str(tmp_path)],
        )

    assert result.exit_code == 0, result.stdout

    repos = json.loads((tmp_path / "lib__repositories.json").read_text())
    arts = json.loads((tmp_path / "lib__foo__artifacts.json").read_text())
    assert repos[0]["name"] == "lib/foo"
    assert arts[0]["digest"] == "sha256:abc"
```

- [ ] **Step 2 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/integration/test_cli_dev_capture.py -v
```

Expected : `dev capture` introuvable.

- [ ] **Step 3 : Implémenter `hub2hub/cli/dev.py` (remplacement complet)**

```python
"""Sous-groupe de commandes internes (dev / debug)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from hub2hub.cli._di import build_container

app = typer.Typer(name="dev", help="Outils de développement (capture de fixtures, debug)")


@app.callback()
def _root() -> None:
    """Sous-groupe de commandes internes."""


@app.command("capture")
def capture(
    project: Annotated[str, typer.Option("--project", help="Nom du projet Harbor")],
    repository: Annotated[str, typer.Option("--repository", help="Nom du repository (sans le projet)")],
    output: Annotated[Path, typer.Option("--output", help="Répertoire de sortie pour les fixtures")],
) -> None:
    """Capture en read-only l'état Harbor d'un repo dans des fichiers JSON.

    Produit :
      <output>/<project>__repositories.json
      <output>/<project>__<repo-sanitisé>__artifacts.json
    """
    output.mkdir(parents=True, exist_ok=True)
    container = build_container()

    repos = container.harbor.get_repositories(project)
    arts = container.harbor.get_artifacts(project, repository)

    repos_path = output / f"{project}__repositories.json"
    repos_path.write_text(json.dumps([asdict(r) for r in repos], indent=2))

    sanitized = repository.replace("/", "_")
    arts_path = output / f"{project}__{sanitized}__artifacts.json"
    arts_path.write_text(json.dumps([asdict(a) for a in arts], indent=2))

    typer.echo(f"Wrote {repos_path}")
    typer.echo(f"Wrote {arts_path}")
```

- [ ] **Step 4 : Lancer le test**

```bash
uv run pytest tests/integration/test_cli_dev_capture.py -v
```

Expected : pass.

- [ ] **Step 5 : Commit**

```bash
git add hub2hub/cli/dev.py tests/integration/test_cli_dev_capture.py
git commit -m "feat(python): ajoute commande h2h dev capture (fixtures depuis Harbor)"
```

---

## Groupe 5 — Modules `domain/`

> Pour chaque tâche de ce groupe, l'implémenteur doit **commencer par lire** la fonction Groovy équivalente dans `vars/importProduct.groovy` ou ailleurs (numéro de ligne donné en référence) avant d'écrire le test, pour extraire le comportement réel. Le test précède toujours le code Python.

### Task 13 : `domain/semver.py` — tri sémantique des tags

**Files:**
- Create: `hub2hub/domain/__init__.py`
- Create: `hub2hub/domain/semver.py`
- Create: `tests/unit/domain/__init__.py`
- Create: `tests/unit/domain/test_semver.py`

Référence Groovy : `sortBySemver` (vars/importProduct.groovy:16-52) et `sortBySemverbyField` (vars/importProduct.groovy:53-88). Annotation `@NonCPS` → fonction pure, port direct.

- [ ] **Step 1 : Lire et noter le comportement Groovy**

```bash
sed -n '16,90p' vars/importProduct.groovy
```

Cas à couvrir (à confirmer à la lecture) :
- tri ascendant par défaut, descendant si flag ;
- versions à 1-2-3 composantes (`1`, `1.2`, `1.2.3`) ;
- préfixe `v` toléré (`v1.2.3` ≡ `1.2.3`) ;
- pré-release alphanum (`1.2.3-rc1`) classé avant `1.2.3` ;
- valeur non sémantique : doit être triée à la fin (ou en tête, à confirmer) sans crasher.

- [ ] **Step 2 : Écrire les tests**

`tests/unit/domain/__init__.py` :

```python
```

`tests/unit/domain/test_semver.py` :

```python
import pytest

from hub2hub.domain.semver import sort_semver


def test_basic_ascending_order() -> None:
    assert sort_semver(["1.0.0", "0.9.0", "1.1.0"]) == ["0.9.0", "1.0.0", "1.1.0"]


def test_descending_order() -> None:
    assert sort_semver(["1.0.0", "0.9.0", "1.1.0"], reverse=True) == ["1.1.0", "1.0.0", "0.9.0"]


def test_v_prefix_treated_as_equal() -> None:
    out = sort_semver(["v1.2.3", "1.2.4", "v1.2.2"])
    assert out == ["v1.2.2", "v1.2.3", "1.2.4"]


def test_pre_release_sorts_before_final() -> None:
    out = sort_semver(["1.2.3", "1.2.3-rc1", "1.2.3-alpha"])
    assert out == ["1.2.3-alpha", "1.2.3-rc1", "1.2.3"]


def test_partial_versions_normalized() -> None:
    assert sort_semver(["1", "1.2", "1.2.3"]) == ["1", "1.2", "1.2.3"]


def test_non_semver_values_pushed_to_end() -> None:
    out = sort_semver(["1.0.0", "latest", "2.0.0", "edge"])
    assert out[:2] == ["1.0.0", "2.0.0"]
    assert set(out[2:]) == {"latest", "edge"}


@pytest.mark.parametrize("value", [[], ["v1"]])
def test_edge_cases_short_lists(value: list[str]) -> None:
    assert sort_semver(value) == value
```

- [ ] **Step 3 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/unit/domain/test_semver.py -v
```

Expected : ImportError.

- [ ] **Step 4 : Implémenter `hub2hub/domain/semver.py`**

```python
"""Tri sémantique des tags d'images.

Port direct de sortBySemver / sortBySemverbyField (vars/importProduct.groovy:16-88).
Fonction pure : aucun I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SEMVER_RE = re.compile(
    r"""^v?
        (?P<major>\d+)
        (?:\.(?P<minor>\d+))?
        (?:\.(?P<patch>\d+))?
        (?:-(?P<prerelease>[0-9A-Za-z.-]+))?
        $""",
    re.VERBOSE,
)


@dataclass(frozen=True, order=True)
class _Key:
    is_non_semver: int  # 1 → pousse en fin de tri
    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease_rank: int = 1  # 0 si pré-release (sorts avant final), 1 si final
    prerelease: str = ""


def _key(value: str) -> _Key:
    m = _SEMVER_RE.match(value.strip())
    if not m:
        return _Key(is_non_semver=1)
    major = int(m.group("major"))
    minor = int(m.group("minor") or 0)
    patch = int(m.group("patch") or 0)
    pre = m.group("prerelease") or ""
    return _Key(
        is_non_semver=0,
        major=major,
        minor=minor,
        patch=patch,
        prerelease_rank=0 if pre else 1,
        prerelease=pre,
    )


def sort_semver(values: list[str], *, reverse: bool = False) -> list[str]:
    semver = [v for v in values if _key(v).is_non_semver == 0]
    others = [v for v in values if _key(v).is_non_semver == 1]
    semver.sort(key=_key, reverse=reverse)
    return [*semver, *others]
```

- [ ] **Step 5 : Lancer**

```bash
uv run pytest tests/unit/domain/test_semver.py -v
```

Expected : 7 tests pass.

- [ ] **Step 6 : Commit**

```bash
git add hub2hub/domain/__init__.py hub2hub/domain/semver.py tests/unit/domain/__init__.py tests/unit/domain/test_semver.py
git commit -m "feat(domain): ajoute sort_semver (port de sortBySemver Groovy)"
```

---

### Task 14 : `domain/properties.py` — parsing du `properties.yml`

**Files:**
- Create: `hub2hub/domain/properties.py`
- Create: `tests/unit/domain/test_properties.py`
- Create: `tests/fixtures/synthetic/properties_minimal.yml`
- Create: `tests/fixtures/synthetic/properties_full.yml`

Référence Groovy : `setProperties` (vars/importProduct.groovy:1292-1347) + `resources/properties.yml.template`.

- [ ] **Step 1 : Lire la référence**

```bash
sed -n '1292,1347p' vars/importProduct.groovy
cat resources/properties.yml.template
```

Champs identifiés (à confirmer à la lecture) :

- `source.registry` (str, obligatoire — ex. `docker.io`)
- `source.repository` (str, obligatoire — ex. `library/busybox`)
- `destination.harbor` (str, obligatoire — `blue|orange|both`)
- `destination.project` (str, obligatoire)
- `destination.repository` (str, obligatoire)
- `tags.include_regex` (str, optionnel)
- `tags.exclude_regex` (list[str], optionnel)
- `tags.semver_only` (bool, défaut true)
- `flags.add_apt_repos` (bool, défaut false)
- `flags.add_yum_repos` (bool, défaut false)
- `flags.update_keystore` (bool, défaut false)
- `flags.set_timezone` (bool, défaut true)
- `eol.product` (str, optionnel — clé endoflife.date)
- `archive.keep` (int, défaut 2)
- `archive.older_than_days` (int, défaut 30)

- [ ] **Step 2 : Écrire les fixtures**

`tests/fixtures/synthetic/properties_minimal.yml` :

```yaml
source:
  registry: docker.io
  repository: library/busybox
destination:
  harbor: blue
  project: lib
  repository: busybox
```

`tests/fixtures/synthetic/properties_full.yml` :

```yaml
source:
  registry: docker.io
  repository: rancher/k3s
destination:
  harbor: both
  project: lib
  repository: k3s
tags:
  include_regex: "^v\\d+\\.\\d+\\.\\d+$"
  exclude_regex:
    - "-rc"
  semver_only: true
flags:
  add_apt_repos: true
  add_yum_repos: false
  update_keystore: true
  set_timezone: true
eol:
  product: kubernetes
archive:
  keep: 3
  older_than_days: 60
```

- [ ] **Step 3 : Écrire les tests**

`tests/unit/domain/test_properties.py` :

```python
from pathlib import Path

import pytest

from hub2hub.domain.properties import Properties, parse_properties
from hub2hub.errors import PropertiesValidationError

FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


def test_parse_minimal_applies_defaults() -> None:
    p = parse_properties((FIXTURES / "properties_minimal.yml").read_text())

    assert isinstance(p, Properties)
    assert p.source.registry == "docker.io"
    assert p.source.repository == "library/busybox"
    assert p.destination.harbor == "blue"
    assert p.tags.semver_only is True   # défaut
    assert p.tags.exclude_regex == []    # défaut
    assert p.flags.set_timezone is True  # défaut
    assert p.archive.keep == 2
    assert p.archive.older_than_days == 30
    assert p.eol.product is None


def test_parse_full_overrides_defaults() -> None:
    p = parse_properties((FIXTURES / "properties_full.yml").read_text())

    assert p.destination.harbor == "both"
    assert p.tags.include_regex == r"^v\d+\.\d+\.\d+$"
    assert p.tags.exclude_regex == ["-rc"]
    assert p.flags.add_apt_repos is True
    assert p.eol.product == "kubernetes"
    assert p.archive.keep == 3


def test_missing_required_field_raises() -> None:
    yaml = """
    source:
      registry: docker.io
    destination:
      harbor: blue
      project: lib
      repository: r
    """
    with pytest.raises(PropertiesValidationError):
        parse_properties(yaml)


def test_invalid_harbor_choice_raises() -> None:
    yaml = """
    source:
      registry: docker.io
      repository: a/b
    destination:
      harbor: purple
      project: lib
      repository: r
    """
    with pytest.raises(PropertiesValidationError):
        parse_properties(yaml)


def test_invalid_yaml_raises() -> None:
    with pytest.raises(PropertiesValidationError):
        parse_properties("source: [unbalanced")
```

- [ ] **Step 4 : Ajouter PyYAML aux dépendances**

Modifier `pyproject.toml` — ajouter `"pyyaml>=6.0"` dans `[project] dependencies` puis :

```bash
uv sync
```

- [ ] **Step 5 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/unit/domain/test_properties.py -v
```

Expected : ImportError.

- [ ] **Step 6 : Implémenter `hub2hub/domain/properties.py`**

```python
"""Parsing et validation du properties.yml d'un produit.

Référence : vars/importProduct.groovy:1292-1347 (setProperties)
et resources/properties.yml.template.
"""

from __future__ import annotations

from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from hub2hub.errors import PropertiesValidationError


class Source(BaseModel):
    registry: str
    repository: str


class Destination(BaseModel):
    harbor: Literal["blue", "orange", "both"]
    project: str
    repository: str


class TagsSpec(BaseModel):
    include_regex: str | None = None
    exclude_regex: list[str] = Field(default_factory=list)
    semver_only: bool = True


class Flags(BaseModel):
    add_apt_repos: bool = False
    add_yum_repos: bool = False
    update_keystore: bool = False
    set_timezone: bool = True


class Eol(BaseModel):
    product: str | None = None


class Archive(BaseModel):
    keep: int = 2
    older_than_days: int = 30


class Properties(BaseModel):
    source: Source
    destination: Destination
    tags: TagsSpec = Field(default_factory=TagsSpec)
    flags: Flags = Field(default_factory=Flags)
    eol: Eol = Field(default_factory=Eol)
    archive: Archive = Field(default_factory=Archive)


def parse_properties(text: str) -> Properties:
    """Parse et valide un properties.yml. Lève PropertiesValidationError en cas d'erreur."""
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise PropertiesValidationError(f"YAML invalide : {e}") from e
    if not isinstance(raw, dict):
        raise PropertiesValidationError("Le document YAML racine doit être un mapping")
    try:
        return Properties.model_validate(raw)
    except ValidationError as e:
        raise PropertiesValidationError(str(e)) from e
```

- [ ] **Step 7 : Lancer**

```bash
uv run pytest tests/unit/domain/test_properties.py -v
```

Expected : 5 tests pass.

- [ ] **Step 8 : Commit**

```bash
git add hub2hub/domain/properties.py tests/unit/domain/test_properties.py tests/fixtures/synthetic/properties_*.yml pyproject.toml uv.lock
git commit -m "feat(domain): ajoute parse_properties (port de setProperties Groovy)"
```

---

### Task 15 : `domain/labels.py` — construction des labels `fr.sncf.h2h.*`

**Files:**
- Create: `hub2hub/domain/labels.py`
- Create: `tests/unit/domain/test_labels.py`

Référence Groovy : chercher les littéraux `fr.sncf.h2h.` dans `vars/importProduct.groovy` :

```bash
grep -n 'fr\.sncf\.h2h' vars/importProduct.groovy
```

Labels à reproduire (à confirmer à la lecture) :
- `fr.sncf.h2h.source.registry`
- `fr.sncf.h2h.source.repository`
- `fr.sncf.h2h.source.tag`
- `fr.sncf.h2h.source.digest`
- `fr.sncf.h2h.import.date` (ISO 8601)
- `fr.sncf.h2h.import.harbor` (blue|orange|both)
- `fr.sncf.h2h.eol.product`
- `fr.sncf.h2h.eol.date`

- [ ] **Step 1 : Lire les références Groovy**

```bash
grep -n 'fr\.sncf\.h2h' vars/importProduct.groovy
```

- [ ] **Step 2 : Écrire les tests**

`tests/unit/domain/test_labels.py` :

```python
from datetime import UTC, datetime

from hub2hub.domain.labels import build_labels


def test_required_labels_present() -> None:
    labels = build_labels(
        src_registry="docker.io",
        src_repository="library/busybox",
        src_tag="1.36",
        src_digest="sha256:abc",
        import_date=datetime(2026, 5, 21, 10, 30, tzinfo=UTC),
        harbor="blue",
        eol_product=None,
        eol_date=None,
    )

    assert labels["fr.sncf.h2h.source.registry"] == "docker.io"
    assert labels["fr.sncf.h2h.source.repository"] == "library/busybox"
    assert labels["fr.sncf.h2h.source.tag"] == "1.36"
    assert labels["fr.sncf.h2h.source.digest"] == "sha256:abc"
    assert labels["fr.sncf.h2h.import.date"] == "2026-05-21T10:30:00+00:00"
    assert labels["fr.sncf.h2h.import.harbor"] == "blue"
    assert "fr.sncf.h2h.eol.product" not in labels
    assert "fr.sncf.h2h.eol.date" not in labels


def test_eol_labels_included_when_provided() -> None:
    labels = build_labels(
        src_registry="docker.io",
        src_repository="library/redis",
        src_tag="7.2",
        src_digest="sha256:def",
        import_date=datetime(2026, 5, 21, tzinfo=UTC),
        harbor="both",
        eol_product="redis",
        eol_date="2025-12-31",
    )

    assert labels["fr.sncf.h2h.eol.product"] == "redis"
    assert labels["fr.sncf.h2h.eol.date"] == "2025-12-31"
```

- [ ] **Step 3 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/unit/domain/test_labels.py -v
```

- [ ] **Step 4 : Implémenter `hub2hub/domain/labels.py`**

```python
"""Construction des labels OCI fr.sncf.h2h.* apposés sur les images importées."""

from __future__ import annotations

from datetime import datetime


def build_labels(
    *,
    src_registry: str,
    src_repository: str,
    src_tag: str,
    src_digest: str,
    import_date: datetime,
    harbor: str,
    eol_product: str | None,
    eol_date: str | None,
) -> dict[str, str]:
    labels: dict[str, str] = {
        "fr.sncf.h2h.source.registry": src_registry,
        "fr.sncf.h2h.source.repository": src_repository,
        "fr.sncf.h2h.source.tag": src_tag,
        "fr.sncf.h2h.source.digest": src_digest,
        "fr.sncf.h2h.import.date": import_date.isoformat(),
        "fr.sncf.h2h.import.harbor": harbor,
    }
    if eol_product:
        labels["fr.sncf.h2h.eol.product"] = eol_product
    if eol_date:
        labels["fr.sncf.h2h.eol.date"] = eol_date
    return labels
```

- [ ] **Step 5 : Lancer**

```bash
uv run pytest tests/unit/domain/test_labels.py -v
```

Expected : 2 tests pass.

- [ ] **Step 6 : Commit**

```bash
git add hub2hub/domain/labels.py tests/unit/domain/test_labels.py
git commit -m "feat(domain): ajoute build_labels (fr.sncf.h2h.*)"
```

---

### Task 16 : `domain/eol.py` — parse d'un tableau Markdown EOL + résolution

**Files:**
- Create: `hub2hub/domain/eol.py`
- Create: `tests/unit/domain/test_eol.py`
- Create: `tests/fixtures/synthetic/eol_kubernetes.md`

Référence Groovy : `parseMarkdownTable` (vars/importProduct.groovy:1509-1521) et `fetchEolDetails` (vars/importProduct.groovy:1522-1606). On porte la **partie pure** (parsing + résolution) en Phase A ; l'appel HTTP réel (`endoflife.date/api/<product>.md`) ira en Phase B dans un adaptateur.

- [ ] **Step 1 : Lire les références Groovy**

```bash
sed -n '1509,1606p' vars/importProduct.groovy
```

Comportement à confirmer :
- entrée : texte Markdown contenant un tableau avec colonnes `releaseCycle`, `eol` (et autres) ;
- `fetchEolDetails` retourne, pour un tag donné, la date EOL si le tag matche un `releaseCycle` ;
- gestion des cas : EOL absent, EOL passé, EOL futur, EOL booléen `false`.

- [ ] **Step 2 : Écrire la fixture Markdown**

`tests/fixtures/synthetic/eol_kubernetes.md` :

```markdown
| releaseCycle | eol        | latest   |
|--------------|------------|----------|
| 1.28         | 2024-10-28 | 1.28.15  |
| 1.29         | 2025-02-28 | 1.29.10  |
| 1.30         | 2026-06-30 | 1.30.5   |
| 1.31         | false      | 1.31.0   |
```

- [ ] **Step 3 : Écrire les tests**

`tests/unit/domain/test_eol.py` :

```python
from pathlib import Path

import pytest

from hub2hub.domain.eol import (
    EolEntry,
    parse_markdown_table,
    resolve_eol_for_tag,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "synthetic" / "eol_kubernetes.md"


def test_parse_markdown_table_returns_rows() -> None:
    entries = parse_markdown_table(FIXTURE.read_text())

    assert entries == [
        EolEntry(release_cycle="1.28", eol="2024-10-28"),
        EolEntry(release_cycle="1.29", eol="2025-02-28"),
        EolEntry(release_cycle="1.30", eol="2026-06-30"),
        EolEntry(release_cycle="1.31", eol="false"),
    ]


def test_parse_markdown_table_empty_input() -> None:
    assert parse_markdown_table("") == []


@pytest.mark.parametrize(
    "tag,expected",
    [
        ("1.28.5", "2024-10-28"),
        ("v1.29.10", "2025-02-28"),
        ("1.30.0", "2026-06-30"),
        ("1.31.0", None),       # eol=false → pas de date
        ("1.32.0", None),       # cycle inconnu
        ("latest", None),
    ],
)
def test_resolve_eol_for_tag(tag: str, expected: str | None) -> None:
    entries = parse_markdown_table(FIXTURE.read_text())
    assert resolve_eol_for_tag(tag, entries) == expected
```

- [ ] **Step 4 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/unit/domain/test_eol.py -v
```

- [ ] **Step 5 : Implémenter `hub2hub/domain/eol.py`**

```python
"""Parsing du tableau Markdown retourné par endoflife.date et résolution EOL par tag.

Référence : vars/importProduct.groovy:1509-1606.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CYCLE_RE_CACHE: dict[str, re.Pattern[str]] = {}


@dataclass(frozen=True)
class EolEntry:
    release_cycle: str
    eol: str  # "YYYY-MM-DD" ou "false" ou autre chaîne brute


def parse_markdown_table(text: str) -> list[EolEntry]:
    """Extrait les lignes (releaseCycle, eol) d'un tableau Markdown.

    Tolère colonnes supplémentaires. Ignore les lignes vides et la ligne séparateur.
    """
    if not text.strip():
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return []

    header_cells = [c.strip().lower() for c in lines[0].strip("|").split("|")]
    try:
        i_cycle = header_cells.index("releasecycle")
        i_eol = header_cells.index("eol")
    except ValueError:
        return []

    entries: list[EolEntry] = []
    for line in lines[2:]:  # skip header + séparateur
        cells = [c.strip() for c in line.strip("|").split("|")]
        if max(i_cycle, i_eol) >= len(cells):
            continue
        entries.append(EolEntry(release_cycle=cells[i_cycle], eol=cells[i_eol]))
    return entries


def resolve_eol_for_tag(tag: str, entries: list[EolEntry]) -> str | None:
    """Retourne la date EOL (YYYY-MM-DD) pour un tag, ou None si inconnue ou désactivée."""
    normalized = tag.lstrip("v")
    for entry in entries:
        if entry.eol in ("", "false", "False"):
            continue
        pattern = _CYCLE_RE_CACHE.setdefault(
            entry.release_cycle,
            re.compile(rf"^{re.escape(entry.release_cycle)}(\.|$)"),
        )
        if pattern.match(normalized):
            return entry.eol
    return None
```

- [ ] **Step 6 : Lancer**

```bash
uv run pytest tests/unit/domain/test_eol.py -v
```

Expected : 8 tests pass.

- [ ] **Step 7 : Commit**

```bash
git add hub2hub/domain/eol.py tests/unit/domain/test_eol.py tests/fixtures/synthetic/eol_kubernetes.md
git commit -m "feat(domain): ajoute parse_markdown_table + resolve_eol_for_tag"
```

---

### Task 17 : `domain/tag_filter.py` — calcul des tags à importer

**Files:**
- Create: `hub2hub/domain/tag_filter.py`
- Create: `tests/unit/domain/test_tag_filter.py`

C'est le **cœur métier**, l'équivalent de `retrieveTagsToImport` (vars/importProduct.groovy:1607-1804). Fonction pure :

```
(src_tags, properties, harbor_state, now) → TagsDecision
```

avec `TagsDecision = (to_import, to_update, to_delete)`. Règles connues d'après la mémoire `coding_conventions` :

- archive tags : suffix `_YYYYMMDD` ; conservation 30 jours, garder 2 plus récents par tag (logique propre à `purge`, séparée — cf. Task 18) ;
- **délai 7 jours** : si le digest source d'un tag a changé < 7 j, on attend ;
- exclusions regex configurables dans `properties.tags.exclude_regex` ;
- `semver_only` : si vrai, ignorer les tags non sémantiques.

- [ ] **Step 1 : Lire la référence Groovy**

```bash
sed -n '1607,1804p' vars/importProduct.groovy
```

Noter les variables/branches : initialiser un brouillon de la fonction à partir des cases observés.

- [ ] **Step 2 : Écrire les tests (couvrir tous les cas listés)**

`tests/unit/domain/test_tag_filter.py` :

```python
from datetime import UTC, datetime, timedelta

import pytest

from hub2hub.domain.properties import Properties, parse_properties
from hub2hub.domain.tag_filter import HarborTagState, TagsDecision, compute_tags_to_import


def _props(yaml: str) -> Properties:
    return parse_properties(yaml)


BASE_YAML = """
source:
  registry: docker.io
  repository: library/busybox
destination:
  harbor: blue
  project: lib
  repository: busybox
tags:
  semver_only: true
"""

NOW = datetime(2026, 5, 21, 12, 0, tzinfo=UTC)


def test_all_new_tags_imported() -> None:
    decision = compute_tags_to_import(
        src_tags=["1.36", "1.37"],
        src_digests={"1.36": ("sha256:a", NOW - timedelta(days=30)), "1.37": ("sha256:b", NOW - timedelta(days=30))},
        properties=_props(BASE_YAML),
        harbor_state={},
        now=NOW,
    )

    assert decision == TagsDecision(to_import=["1.36", "1.37"], to_update=[], to_delete=[])


def test_already_present_with_same_digest_skipped() -> None:
    harbor_state = {
        "1.36": HarborTagState(digest="sha256:a", push_time=NOW - timedelta(days=10)),
    }

    decision = compute_tags_to_import(
        src_tags=["1.36"],
        src_digests={"1.36": ("sha256:a", NOW - timedelta(days=30))},
        properties=_props(BASE_YAML),
        harbor_state=harbor_state,
        now=NOW,
    )

    assert decision.to_import == []
    assert decision.to_update == []


def test_digest_changed_recently_waits_7_days() -> None:
    harbor_state = {
        "1.36": HarborTagState(digest="sha256:old", push_time=NOW - timedelta(days=30)),
    }
    src_digests = {"1.36": ("sha256:new", NOW - timedelta(days=3))}

    decision = compute_tags_to_import(
        src_tags=["1.36"],
        src_digests=src_digests,
        properties=_props(BASE_YAML),
        harbor_state=harbor_state,
        now=NOW,
    )

    assert "1.36" not in decision.to_import
    assert "1.36" not in decision.to_update


def test_digest_changed_more_than_7_days_updates() -> None:
    harbor_state = {
        "1.36": HarborTagState(digest="sha256:old", push_time=NOW - timedelta(days=30)),
    }
    src_digests = {"1.36": ("sha256:new", NOW - timedelta(days=10))}

    decision = compute_tags_to_import(
        src_tags=["1.36"],
        src_digests=src_digests,
        properties=_props(BASE_YAML),
        harbor_state=harbor_state,
        now=NOW,
    )

    assert "1.36" in decision.to_update


def test_exclude_regex_filters() -> None:
    yaml = BASE_YAML + "\n  exclude_regex:\n    - '-rc'\n    - '-beta'\n"
    decision = compute_tags_to_import(
        src_tags=["1.36", "1.37-rc1", "1.37-beta"],
        src_digests={t: ("sha256:x", NOW - timedelta(days=30)) for t in ["1.36", "1.37-rc1", "1.37-beta"]},
        properties=_props(yaml),
        harbor_state={},
        now=NOW,
    )

    assert decision.to_import == ["1.36"]


def test_semver_only_drops_non_semver_tags() -> None:
    decision = compute_tags_to_import(
        src_tags=["1.36", "latest", "edge"],
        src_digests={t: ("sha256:x", NOW - timedelta(days=30)) for t in ["1.36", "latest", "edge"]},
        properties=_props(BASE_YAML),
        harbor_state={},
        now=NOW,
    )

    assert decision.to_import == ["1.36"]


def test_include_regex_keeps_only_matches() -> None:
    yaml = BASE_YAML + "\n  include_regex: '^1\\\\.36$'\n"
    decision = compute_tags_to_import(
        src_tags=["1.36", "1.37"],
        src_digests={t: ("sha256:x", NOW - timedelta(days=30)) for t in ["1.36", "1.37"]},
        properties=_props(yaml),
        harbor_state={},
        now=NOW,
    )

    assert decision.to_import == ["1.36"]


def test_to_delete_when_tag_absent_from_source() -> None:
    harbor_state = {
        "1.35": HarborTagState(digest="sha256:gone", push_time=NOW - timedelta(days=90)),
        "1.36": HarborTagState(digest="sha256:a", push_time=NOW - timedelta(days=10)),
    }
    decision = compute_tags_to_import(
        src_tags=["1.36"],
        src_digests={"1.36": ("sha256:a", NOW - timedelta(days=30))},
        properties=_props(BASE_YAML),
        harbor_state=harbor_state,
        now=NOW,
    )

    assert "1.35" in decision.to_delete


@pytest.mark.parametrize("bad_regex", ["[unclosed", "*invalid"])
def test_invalid_regex_raises(bad_regex: str) -> None:
    from hub2hub.errors import PropertiesValidationError

    yaml = BASE_YAML + f"\n  include_regex: '{bad_regex}'\n"
    with pytest.raises(PropertiesValidationError):
        compute_tags_to_import(
            src_tags=["1.36"],
            src_digests={"1.36": ("sha256:x", NOW - timedelta(days=30))},
            properties=_props(yaml),
            harbor_state={},
            now=NOW,
        )
```

- [ ] **Step 3 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/unit/domain/test_tag_filter.py -v
```

- [ ] **Step 4 : Implémenter `hub2hub/domain/tag_filter.py`**

```python
"""Calcul des tags à importer / mettre à jour / supprimer.

Port de retrieveTagsToImport (vars/importProduct.groovy:1607-1804).
Fonction pure : aucun I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from hub2hub.domain.properties import Properties
from hub2hub.domain.semver import sort_semver
from hub2hub.errors import PropertiesValidationError

DIGEST_CHANGE_GRACE = timedelta(days=7)
_SEMVER_RE = re.compile(r"^v?\d+(\.\d+){0,2}(-[0-9A-Za-z.-]+)?$")


@dataclass(frozen=True)
class HarborTagState:
    digest: str
    push_time: datetime


@dataclass(frozen=True)
class TagsDecision:
    to_import: list[str] = field(default_factory=list)
    to_update: list[str] = field(default_factory=list)
    to_delete: list[str] = field(default_factory=list)


def _compile(pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as e:
        raise PropertiesValidationError(f"regex invalide '{pattern}': {e}") from e


def compute_tags_to_import(
    *,
    src_tags: list[str],
    src_digests: dict[str, tuple[str, datetime]],
    properties: Properties,
    harbor_state: dict[str, HarborTagState],
    now: datetime,
) -> TagsDecision:
    include = _compile(properties.tags.include_regex) if properties.tags.include_regex else None
    excludes = [_compile(p) for p in properties.tags.exclude_regex]

    candidates: list[str] = []
    for tag in src_tags:
        if properties.tags.semver_only and not _SEMVER_RE.match(tag):
            continue
        if include and not include.search(tag):
            continue
        if any(ex.search(tag) for ex in excludes):
            continue
        candidates.append(tag)

    candidates = sort_semver(candidates)

    to_import: list[str] = []
    to_update: list[str] = []
    for tag in candidates:
        src_digest, src_push_time = src_digests[tag]
        harbor = harbor_state.get(tag)
        if harbor is None:
            to_import.append(tag)
            continue
        if harbor.digest == src_digest:
            continue
        if now - src_push_time < DIGEST_CHANGE_GRACE:
            continue
        to_update.append(tag)

    src_set = set(src_tags)
    to_delete = [tag for tag in harbor_state if tag not in src_set]

    return TagsDecision(to_import=to_import, to_update=to_update, to_delete=to_delete)
```

- [ ] **Step 5 : Lancer**

```bash
uv run pytest tests/unit/domain/test_tag_filter.py -v
```

Expected : 11 tests pass.

- [ ] **Step 6 : Commit**

```bash
git add hub2hub/domain/tag_filter.py tests/unit/domain/test_tag_filter.py
git commit -m "feat(domain): ajoute compute_tags_to_import (port de retrieveTagsToImport)"
```

---

### Task 18 : `domain/purge.py` — sélection des tags d'archive à purger

**Files:**
- Create: `hub2hub/domain/purge.py`
- Create: `tests/unit/domain/test_purge.py`

Référence Groovy : `purgeArchives` (vars/importProduct.groovy:1348-1435). Règle (cf. mémoire `coding_conventions`) : **purge > 30 jours, garder 2 plus récents par tag de base**.

- [ ] **Step 1 : Lire la référence**

```bash
sed -n '1348,1435p' vars/importProduct.groovy
```

Format d'archive : `<base>_YYYYMMDD`. Exemple : `1.36_20260101`.

- [ ] **Step 2 : Écrire les tests**

`tests/unit/domain/test_purge.py` :

```python
from datetime import UTC, datetime

from hub2hub.domain.purge import compute_archives_to_purge


def test_archives_older_than_30_days_purged_keeping_latest_2() -> None:
    now = datetime(2026, 5, 21, tzinfo=UTC)
    archives = [
        "1.36_20240101",  # > 30 j, doit être purgé si pas dans le top 2
        "1.36_20240201",
        "1.36_20240301",  # plus récent
        "1.36_20240215",
        "1.37_20260201",
        "1.37_20260301",
        "1.37_20260315",  # plus récent
    ]

    purged = compute_archives_to_purge(archives, keep=2, older_than_days=30, now=now)

    assert sorted(purged) == sorted(["1.36_20240101", "1.36_20240201"])


def test_keeps_top_n_when_all_recent() -> None:
    now = datetime(2026, 5, 21, tzinfo=UTC)
    archives = ["1.36_20260520", "1.36_20260519"]
    purged = compute_archives_to_purge(archives, keep=2, older_than_days=30, now=now)
    assert purged == []


def test_ignores_non_archive_tags() -> None:
    now = datetime(2026, 5, 21, tzinfo=UTC)
    archives = ["latest", "1.36", "1.36_20240101"]
    purged = compute_archives_to_purge(archives, keep=2, older_than_days=30, now=now)
    assert purged == []  # un seul archive du cycle 1.36, conservé (< keep)


def test_invalid_date_in_suffix_is_ignored() -> None:
    now = datetime(2026, 5, 21, tzinfo=UTC)
    archives = ["1.36_2024xx01", "1.36_20240101", "1.36_20240201", "1.36_20240301"]
    purged = compute_archives_to_purge(archives, keep=2, older_than_days=30, now=now)
    assert "1.36_2024xx01" not in purged  # mal formé, ignoré
    assert "1.36_20240101" in purged
```

- [ ] **Step 3 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/unit/domain/test_purge.py -v
```

- [ ] **Step 4 : Implémenter `hub2hub/domain/purge.py`**

```python
"""Sélection des tags d'archive à purger.

Référence : vars/importProduct.groovy:1348-1435 (purgeArchives).
Convention : <base>_YYYYMMDD.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta

_ARCHIVE_RE = re.compile(r"^(?P<base>.+)_(?P<date>\d{8})$")


def _parse(tag: str) -> tuple[str, datetime] | None:
    m = _ARCHIVE_RE.match(tag)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group("date"), "%Y%m%d")
    except ValueError:
        return None
    return m.group("base"), dt


def compute_archives_to_purge(
    archives: list[str],
    *,
    keep: int,
    older_than_days: int,
    now: datetime,
) -> list[str]:
    by_base: dict[str, list[tuple[str, datetime]]] = defaultdict(list)
    for tag in archives:
        parsed = _parse(tag)
        if parsed is None:
            continue
        base, dt = parsed
        by_base[base].append((tag, dt))

    threshold = now.replace(tzinfo=None) - timedelta(days=older_than_days)
    purged: list[str] = []
    for entries in by_base.values():
        entries.sort(key=lambda e: e[1], reverse=True)
        for tag, dt in entries[keep:]:
            if dt < threshold:
                purged.append(tag)
    return purged
```

- [ ] **Step 5 : Lancer**

```bash
uv run pytest tests/unit/domain/test_purge.py -v
```

Expected : 4 tests pass.

- [ ] **Step 6 : Commit**

```bash
git add hub2hub/domain/purge.py tests/unit/domain/test_purge.py
git commit -m "feat(domain): ajoute compute_archives_to_purge (port de purgeArchives)"
```

---

### Task 19 : `domain/plan.py` — construction d'un `ImportPlan` par tag

**Files:**
- Create: `hub2hub/domain/plan.py`
- Create: `tests/unit/domain/test_plan.py`

`ImportPlan` est la valeur passée au use-case Phase C pour matérialiser le Dockerfile et l'appel à BuildKit. Réunit le tag, le digest, les flags, les labels et le contexte EOL. Reste pur (calcul à partir des inputs résolus en amont).

- [ ] **Step 1 : Écrire les tests**

`tests/unit/domain/test_plan.py` :

```python
from datetime import UTC, datetime

from hub2hub.domain.plan import ImportPlan, build_plan
from hub2hub.domain.properties import parse_properties

YAML = """
source:
  registry: docker.io
  repository: library/busybox
destination:
  harbor: blue
  project: lib
  repository: busybox
flags:
  add_apt_repos: true
  update_keystore: true
  set_timezone: true
eol:
  product: busybox
"""


def test_build_plan_basic_fields() -> None:
    plan = build_plan(
        tag="1.36",
        properties=parse_properties(YAML),
        src_digest="sha256:abc",
        eol_date="2027-01-01",
        now=datetime(2026, 5, 21, tzinfo=UTC),
    )

    assert isinstance(plan, ImportPlan)
    assert plan.tag == "1.36"
    assert plan.src_image == "docker.io/library/busybox:1.36"
    assert plan.dst_image == "lib/busybox:1.36"
    assert plan.flags["add_apt_repos"] is True
    assert plan.flags["add_yum_repos"] is False
    assert plan.labels["fr.sncf.h2h.source.digest"] == "sha256:abc"
    assert plan.labels["fr.sncf.h2h.eol.date"] == "2027-01-01"


def test_build_plan_without_eol() -> None:
    yaml_no_eol = """
    source:
      registry: docker.io
      repository: library/busybox
    destination:
      harbor: blue
      project: lib
      repository: busybox
    """
    plan = build_plan(
        tag="1.36",
        properties=parse_properties(yaml_no_eol),
        src_digest="sha256:abc",
        eol_date=None,
        now=datetime(2026, 5, 21, tzinfo=UTC),
    )

    assert "fr.sncf.h2h.eol.product" not in plan.labels
    assert "fr.sncf.h2h.eol.date" not in plan.labels
```

- [ ] **Step 2 : Lancer pour vérifier l'échec**

```bash
uv run pytest tests/unit/domain/test_plan.py -v
```

- [ ] **Step 3 : Implémenter `hub2hub/domain/plan.py`**

```python
"""Construction d'un plan d'import pour un tag donné.

Le plan agrège toutes les informations nécessaires au use-case product_import
pour générer un Dockerfile et exécuter BuildKit. C'est une valeur, pas un acteur.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from hub2hub.domain.labels import build_labels
from hub2hub.domain.properties import Properties


@dataclass(frozen=True)
class ImportPlan:
    tag: str
    src_image: str        # "<registry>/<repository>:<tag>"
    dst_image: str        # "<project>/<repository>:<tag>"
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
```

- [ ] **Step 4 : Lancer**

```bash
uv run pytest tests/unit/domain/test_plan.py -v
```

Expected : 2 tests pass.

- [ ] **Step 5 : Commit**

```bash
git add hub2hub/domain/plan.py tests/unit/domain/test_plan.py
git commit -m "feat(domain): ajoute build_plan (ImportPlan par tag)"
```

---

## Groupe 6 — Capture de fixtures depuis la production

### Task 20 : Capturer les fixtures de prod (opérationnel, non code)

**Files:**
- Create: `tests/fixtures/captured/.gitkeep`
- Create: `docs/superpowers/runbooks/capture-fixtures.md`

Cette tâche est **opérationnelle**, pas de code à écrire. Le but est de remplir `tests/fixtures/captured/` avec ~20 captures Harbor de produits réels représentatifs.

- [ ] **Step 1 : Écrire le runbook**

`docs/superpowers/runbooks/capture-fixtures.md` :

```markdown
# Runbook — Capture de fixtures Hub2Hub

## But

Constituer un jeu de fixtures Harbor depuis la prod pour le développement et
les snapshot tests de la Phase A.

## Pré-requis

- Accès lecture au Harbor de production (`H2H_HARBOR_URL`, robot account
  read-only `pic-dosn_hcr-prod-sharedlibs` ou équivalent).
- Variables d'environnement `H2H_*` valorisées (cf. spec §6.1).
- Image `h2h-cli` buildée localement (`docker build -t h2h-cli:dev .`) ou
  exécution via `uv run h2h`.

## Sélection des produits

Capturer **au moins** un produit pour chacun des cas suivants :

| Cas                                | Suggestion             |
|------------------------------------|------------------------|
| Produit simple (peu de tags)       | `library/busybox`      |
| Produit semver dense               | `rancher/k3s`          |
| Produit avec EOL                   | `library/redis`        |
| Produit avec exclusions regex      | (à choisir)            |
| Produit avec digest changeant      | `library/nginx:stable` |
| Produit multi-tag (alias)          | (à choisir)            |
| Produit déjà archivé               | (à choisir)            |
| Produit avec proxy-cache amont     | (à choisir)            |

Au total : viser 10 à 20 captures.

## Procédure

Pour chaque produit retenu :

```bash
uv run h2h dev capture \
  --project <project> \
  --repository <repository> \
  --output tests/fixtures/captured/
```

## Anonymisation

Avant commit : grep le contenu pour vérifier qu'aucune donnée sensible n'a fuité.
Les noms d'agents (`robot$…`), URLs internes et tokens ne doivent **pas**
apparaître dans les fichiers JSON.

## Commit

```bash
git add tests/fixtures/captured/
git commit -m "test(fixtures): capture initiale de N fixtures Harbor prod"
```
```

- [ ] **Step 2 : Créer le répertoire**

```bash
mkdir -p tests/fixtures/captured
touch tests/fixtures/captured/.gitkeep
```

- [ ] **Step 3 : Commit du runbook (la collecte effective vient ensuite)**

```bash
git add tests/fixtures/captured/.gitkeep docs/superpowers/runbooks/capture-fixtures.md
git commit -m "docs(runbook): ajoute le runbook de capture de fixtures Hub2Hub"
```

- [ ] **Step 4 : Exécuter la capture (opérationnel)**

Exécuter le runbook ci-dessus avec un compte robot read-only sur la prod. Cette exécution **n'est pas reproductible en CI** ; le résultat est commité directement.

- [ ] **Step 5 : Commit des fixtures capturées**

```bash
git add tests/fixtures/captured/
git commit -m "test(fixtures): capture initiale de N fixtures Harbor (cf. runbook)"
```

---

## Groupe 7 — CI GitLab + Dockerfile squelette

### Task 21 : Ajouter les jobs Python au `.gitlab-ci.yml`

**Files:**
- Modify: `.gitlab-ci.yml`

But : exécuter `lint`, `test:unit`, `test:integration` à chaque push.

- [ ] **Step 1 : Lire l'existant**

```bash
cat .gitlab-ci.yml | head -40
```

- [ ] **Step 2 : Ajouter les jobs Python à la fin du fichier**

Ajouter en bas de `.gitlab-ci.yml` :

```yaml
# ──────────────── Python (Phase A) ────────────────

.python_base:
  image: python:3.12-slim
  before_script:
    - pip install --no-cache-dir uv
    - uv sync

python:lint:
  extends: .python_base
  stage: test
  script:
    - uv run ruff check .
    - uv run ruff format --check .
    - uv run mypy hub2hub
  rules:
    - changes:
        - pyproject.toml
        - uv.lock
        - hub2hub/**/*
        - tests/**/*
        - .gitlab-ci.yml

python:test:
  extends: .python_base
  stage: test
  before_script:
    - pip install --no-cache-dir uv
    - apt-get update && apt-get install -y --no-install-recommends git ca-certificates
    - uv sync
  script:
    # Unit + integration en un seul run pour que la couverture agrège
    # le code testé par les deux types de tests.
    - uv run pytest tests/ -v --cov=hub2hub --cov-report=term-missing --cov-fail-under=80
    # Gate spécifique : domain/ doit dépasser 90 %.
    - uv run pytest tests/unit/domain -v --cov=hub2hub.domain --cov-report=term-missing --cov-fail-under=90
  artifacts:
    when: always
    paths:
      - .coverage
    expire_in: 1 week
  rules:
    - changes:
        - pyproject.toml
        - uv.lock
        - hub2hub/**/*
        - tests/**/*
```

Si la section `stages:` n'existe pas en haut, ajouter :

```yaml
stages:
  - test
```

- [ ] **Step 3 : Vérification locale**

Lancer localement les mêmes commandes que la CI exécutera :

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy hub2hub
uv run pytest tests/ -v --cov=hub2hub --cov-fail-under=80
uv run pytest tests/unit/domain -v --cov=hub2hub.domain --cov-fail-under=90
```

Expected : tout passe, coverage global > 80 %, coverage `hub2hub.domain` > 90 %.

- [ ] **Step 4 : Commit**

```bash
git add .gitlab-ci.yml
git commit -m "ci: ajoute jobs Python (lint, test:unit, test:integration)"
```

---

### Task 22 : Dockerfile squelette (image vide, sans skopeo/buildkit encore)

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

Le runtime complet (skopeo + buildctl) est livré en Phase B. Ici on livre une image qui contient juste `h2h` et `python` pour valider l'ENTRYPOINT.

- [ ] **Step 1 : Écrire le Dockerfile minimal**

`Dockerfile` :

```dockerfile
# Phase A — image minimaliste. Phase B ajoute skopeo + buildctl + git.
FROM python:3.12-slim AS build

WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY hub2hub ./hub2hub

RUN pip install --no-cache-dir uv && uv build

FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /src/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

ENTRYPOINT ["h2h"]
CMD ["--help"]
```

- [ ] **Step 2 : Écrire le `.dockerignore`**

`.dockerignore` :

```
.git
.venv
.uv-cache
.pytest_cache
.mypy_cache
.ruff_cache
.coverage
htmlcov
dist
tests
docs
vars
ci
resources
.claude
*.md
```

- [ ] **Step 3 : Build local et smoke test**

```bash
docker build -t h2h-cli:dev .
docker run --rm h2h-cli:dev version
```

Expected : la version `0.1.0-dev` (ou ce qui est dans `pyproject.toml`) s'affiche.

- [ ] **Step 4 : Ajouter le job CI de build d'image**

Modifier `.gitlab-ci.yml` — ajouter après les jobs Python :

```yaml
python:build:image:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  variables:
    DOCKER_TLS_CERTDIR: ""
  script:
    - docker build -t h2h-cli:${CI_COMMIT_SHORT_SHA} .
  rules:
    - if: $CI_COMMIT_BRANCH
      changes:
        - Dockerfile
        - pyproject.toml
        - uv.lock
        - hub2hub/**/*
```

Ajouter `build` à la liste des stages :

```yaml
stages:
  - test
  - build
```

- [ ] **Step 5 : Commit**

```bash
git add Dockerfile .dockerignore .gitlab-ci.yml
git commit -m "feat(image): ajoute Dockerfile squelette et job CI build (Phase A)"
```

---

## Tâche finale — Validation globale Phase A

### Task 23 : Vérification d'ensemble + coverage gate

**Files:**
- Aucun nouveau fichier ; lance la suite complète.

- [ ] **Step 1 : Suite complète**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy hub2hub
uv run pytest -v --cov=hub2hub --cov-report=term-missing --cov-fail-under=80
```

Expected : tout passe.

- [ ] **Step 2 : Vérifier coverage > 90 % sur `domain/`**

```bash
uv run pytest tests/unit/domain -v --cov=hub2hub.domain --cov-report=term-missing --cov-fail-under=90
```

Expected : pass.

- [ ] **Step 3 : Build et smoke runtime**

```bash
docker build -t h2h-cli:phaseA .
docker run --rm h2h-cli:phaseA version
docker run --rm h2h-cli:phaseA --help
docker run --rm h2h-cli:phaseA dev --help
```

Expected : version affichée, sous-groupe `dev` listé avec sa commande `capture`.

- [ ] **Step 4 : Pousser la branche pour la CI**

```bash
git push -u origin feat/python-cli
```

Vérifier que tous les jobs CI passent : `python:lint`, `python:test:unit`, `python:test:integration`, `python:build:image`.

- [ ] **Step 5 : Tag de la fin de Phase A**

```bash
git tag -a v0.1.0-phase-a -m "Phase A — fondations + domain/ + capture"
git push origin v0.1.0-phase-a
```

---

## Critères d'acceptation de la Phase A

Cette phase est livrée quand **tous** les critères suivants sont satisfaits :

- [ ] `uv run ruff check .` passe.
- [ ] `uv run ruff format --check .` passe.
- [ ] `uv run mypy hub2hub` passe (`--strict` global, partiellement laxiste sur adapters/cli).
- [ ] `uv run pytest` passe avec coverage > 80 % global.
- [ ] Coverage `hub2hub.domain` > 90 %.
- [ ] `docker build -t h2h-cli:phaseA .` réussit.
- [ ] `docker run --rm h2h-cli:phaseA version` affiche une version.
- [ ] `tests/fixtures/captured/` contient au moins 10 captures issues de la prod (validé par lecture manuelle).
- [ ] Pipeline GitLab CI vert sur la branche `feat/python-cli`.
- [ ] Aucun import d'une variable d'env hors de `hub2hub/config.py`.
- [ ] Aucun module dans `hub2hub/domain/` n'importe `requests`, `httpx`, `subprocess`, `pathlib.Path` pour ouverture de fichier, ou autre I/O externe (validé par grep manuel).

```bash
# Sanity grep
grep -rn "import requests\|import httpx\|import subprocess" hub2hub/domain/ || echo "OK"
grep -rn "os.environ" hub2hub/ --include='*.py' | grep -v config.py || echo "OK"
```
