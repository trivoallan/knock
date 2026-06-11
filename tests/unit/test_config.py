from pathlib import Path

import pytest
from pydantic import ValidationError

from houba.config import HarborSettings, RegistryConfig, Settings


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOUBA_HARBOR_URL", "https://harbor.example.com")
    monkeypatch.setenv("HOUBA_HARBOR_USER", "robot$houba")
    monkeypatch.setenv("HOUBA_HARBOR_PASSWORD", "s3cret")
    monkeypatch.setenv("HOUBA_GITLAB_URL", "https://gitlab.example.com")
    monkeypatch.setenv("HOUBA_GITLAB_TOKEN", "glpat-xxx")
    monkeypatch.setenv("HOUBA_GITLAB_GROUP", "eul/houba/products")
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


def test_label_prefix_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """HOUBA_LABEL_PREFIX vaut 'io.houba' par défaut."""
    monkeypatch.setenv("HOUBA_HARBOR_URL", "https://h")
    monkeypatch.setenv("HOUBA_HARBOR_USER", "u")
    monkeypatch.setenv("HOUBA_HARBOR_PASSWORD", "p")
    monkeypatch.setenv("HOUBA_GITLAB_URL", "https://g")
    monkeypatch.setenv("HOUBA_GITLAB_TOKEN", "t")
    monkeypatch.setenv("HOUBA_GITLAB_GROUP", "g")
    monkeypatch.delenv("HOUBA_LABEL_PREFIX", raising=False)

    settings = Settings()
    assert settings.label_prefix == "io.houba"


def test_label_prefix_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """HOUBA_LABEL_PREFIX peut être surchargé via la variable d'environnement."""
    monkeypatch.setenv("HOUBA_HARBOR_URL", "https://h")
    monkeypatch.setenv("HOUBA_HARBOR_USER", "u")
    monkeypatch.setenv("HOUBA_HARBOR_PASSWORD", "p")
    monkeypatch.setenv("HOUBA_GITLAB_URL", "https://g")
    monkeypatch.setenv("HOUBA_GITLAB_TOKEN", "t")
    monkeypatch.setenv("HOUBA_GITLAB_GROUP", "g")
    monkeypatch.setenv("HOUBA_LABEL_PREFIX", "com.example.myorg")

    settings = Settings()
    assert settings.label_prefix == "com.example.myorg"


def test_registry_config_minimal() -> None:
    r = RegistryConfig(host="harbor.corp.example.com")
    assert r.host == "harbor.corp.example.com"
    assert r.username is None
    assert r.password is None
    assert r.tls_verify is True  # default


def test_registry_config_with_credentials() -> None:
    r = RegistryConfig(host="h", username="robot", password="s3cret", tls_verify=False)
    assert r.username == "robot"
    assert r.password.get_secret_value() == "s3cret"
    assert r.tls_verify is False


def test_registry_config_password_masked_in_repr() -> None:
    r = RegistryConfig(host="h", username="u", password="leak-me")
    assert "leak-me" not in repr(r)


def test_registry_config_username_without_password_rejected() -> None:
    with pytest.raises(ValidationError, match="together"):
        RegistryConfig(host="h", username="robot")


def test_registry_config_password_without_username_rejected() -> None:
    with pytest.raises(ValidationError, match="together"):
        RegistryConfig(host="h", password="s3cret")


def test_registry_config_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        RegistryConfig(host="h", typpo="x")
