from pathlib import Path

import pytest
from pydantic import ValidationError

from hub2hub.config import HarborSettings, Settings


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOUBA_HARBOR_URL", "https://harbor.example.com")
    monkeypatch.setenv("HOUBA_HARBOR_USER", "robot$h2h")
    monkeypatch.setenv("HOUBA_HARBOR_PASSWORD", "s3cret")
    monkeypatch.setenv("HOUBA_GITLAB_URL", "https://gitlab.example.com")
    monkeypatch.setenv("HOUBA_GITLAB_TOKEN", "glpat-xxx")
    monkeypatch.setenv("HOUBA_GITLAB_GROUP", "eul/h2h/products")
    monkeypatch.setenv("HOUBA_WORK_DIR", str(tmp_path))

    settings = Settings()

    assert settings.harbor.url == "https://harbor.example.com"
    assert settings.harbor.password.get_secret_value() == "s3cret"
    assert settings.gitlab.token.get_secret_value() == "glpat-xxx"
    assert settings.work_dir == tmp_path
    assert settings.log_format == "text"  # défaut
    assert settings.log_level == "INFO"  # défaut


def test_settings_secrets_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOUBA_HARBOR_URL", "https://h")
    monkeypatch.setenv("HOUBA_HARBOR_USER", "u")
    monkeypatch.setenv("HOUBA_HARBOR_PASSWORD", "s3cret-leak")
    monkeypatch.setenv("HOUBA_GITLAB_URL", "https://g")
    monkeypatch.setenv("HOUBA_GITLAB_TOKEN", "tok-leak")
    monkeypatch.setenv("HOUBA_GITLAB_GROUP", "g")

    settings = Settings()
    text = repr(settings)
    assert "s3cret-leak" not in text
    assert "tok-leak" not in text


def test_settings_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "HOUBA_HARBOR_URL",
        "HOUBA_HARBOR_USER",
        "HOUBA_HARBOR_PASSWORD",
        "HOUBA_GITLAB_URL",
        "HOUBA_GITLAB_TOKEN",
        "HOUBA_GITLAB_GROUP",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_teams_webhook_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOUBA_HARBOR_URL", "https://h")
    monkeypatch.setenv("HOUBA_HARBOR_USER", "u")
    monkeypatch.setenv("HOUBA_HARBOR_PASSWORD", "s")
    monkeypatch.setenv("HOUBA_GITLAB_URL", "https://g")
    monkeypatch.setenv("HOUBA_GITLAB_TOKEN", "t")
    monkeypatch.setenv("HOUBA_GITLAB_GROUP", "grp")
    monkeypatch.delenv("HOUBA_TEAMS_WEBHOOK_URL", raising=False)

    settings = Settings()
    assert settings.teams_webhook_url is None


def test_harbor_settings_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les sous-blocs Settings doivent supporter une instanciation directe pour les tests."""
    h = HarborSettings(url="https://x", user="u", password="p")
    assert h.password.get_secret_value() == "p"


def test_invalid_log_level_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une valeur de `HOUBA_LOG_LEVEL` hors du Literal doit lever ValidationError."""
    monkeypatch.setenv("HOUBA_HARBOR_URL", "https://h")
    monkeypatch.setenv("HOUBA_HARBOR_USER", "u")
    monkeypatch.setenv("HOUBA_HARBOR_PASSWORD", "p")
    monkeypatch.setenv("HOUBA_GITLAB_URL", "https://g")
    monkeypatch.setenv("HOUBA_GITLAB_TOKEN", "t")
    monkeypatch.setenv("HOUBA_GITLAB_GROUP", "g")
    monkeypatch.setenv("HOUBA_LOG_LEVEL", "TRACE")

    with pytest.raises(ValidationError):
        Settings()


def test_endoflife_url_validated_but_str(monkeypatch: pytest.MonkeyPatch) -> None:
    """`endoflife_url` est validé comme URL mais exposé comme `str` pour httpx."""
    monkeypatch.setenv("HOUBA_HARBOR_URL", "https://h")
    monkeypatch.setenv("HOUBA_HARBOR_USER", "u")
    monkeypatch.setenv("HOUBA_HARBOR_PASSWORD", "p")
    monkeypatch.setenv("HOUBA_GITLAB_URL", "https://g")
    monkeypatch.setenv("HOUBA_GITLAB_TOKEN", "t")
    monkeypatch.setenv("HOUBA_GITLAB_GROUP", "g")
    monkeypatch.setenv("HOUBA_ENDOFLIFE_URL", "https://eol.test/api")

    settings = Settings()
    assert isinstance(settings.endoflife_url, str)
    assert settings.endoflife_url == "https://eol.test/api"

    monkeypatch.setenv("HOUBA_ENDOFLIFE_URL", "not-a-url")
    with pytest.raises(ValidationError):
        Settings()
