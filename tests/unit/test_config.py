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
    assert settings.log_level == "INFO"  # défaut


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
    for name in (
        "H2H_HARBOR_URL",
        "H2H_HARBOR_USER",
        "H2H_HARBOR_PASSWORD",
        "H2H_GITLAB_URL",
        "H2H_GITLAB_TOKEN",
        "H2H_GITLAB_GROUP",
    ):
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
