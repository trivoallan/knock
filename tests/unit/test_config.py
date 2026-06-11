from pathlib import Path

import pytest
from pydantic import ValidationError

from houba.config import RegistryConfig, Settings, resolve_registry
from houba.errors import ConfigError


def test_settings_constructs_with_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings() doit fonctionner sans aucune variable d'environnement obligatoire."""
    monkeypatch.delenv("HOUBA_REGISTRIES", raising=False)
    s = Settings()
    assert s.registries == {}
    assert s.label_prefix == "io.houba"
    assert s.log_format == "text"
    assert s.log_level == "INFO"


def test_invalid_log_level_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une valeur de `HOUBA_LOG_LEVEL` hors du Literal doit lever ValidationError."""
    monkeypatch.setenv("HOUBA_LOG_LEVEL", "TRACE")

    with pytest.raises(ValidationError):
        Settings()


def test_label_prefix_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """HOUBA_LABEL_PREFIX vaut 'io.houba' par défaut."""
    monkeypatch.delenv("HOUBA_LABEL_PREFIX", raising=False)
    assert Settings().label_prefix == "io.houba"


def test_label_prefix_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """HOUBA_LABEL_PREFIX peut être surchargé via la variable d'environnement."""
    monkeypatch.setenv("HOUBA_LABEL_PREFIX", "com.example.myorg")
    assert Settings().label_prefix == "com.example.myorg"


def test_work_dir_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOUBA_WORK_DIR", str(tmp_path))
    assert Settings().work_dir == tmp_path


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


def test_registries_roster_empty_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOUBA_REGISTRIES", raising=False)
    assert Settings().registries == {}


def test_registries_roster_from_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "HOUBA_REGISTRIES",
        '{"eu": {"host": "harbor.eu.corp", "username": "robot", "password": "s3cret"},'
        ' "us": {"host": "harbor.us.corp"}}',
    )
    reg = Settings().registries
    assert set(reg) == {"eu", "us"}
    assert reg["eu"].host == "harbor.eu.corp"
    assert reg["eu"].password.get_secret_value() == "s3cret"
    assert reg["us"].username is None


def test_registries_roster_password_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "HOUBA_REGISTRIES",
        '{"eu": {"host": "h", "username": "u", "password": "roster-leak"}}',
    )
    assert "roster-leak" not in repr(Settings())


def test_registries_roster_invalid_entry_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    # username without password → RegistryConfig validator fires during Settings parse
    monkeypatch.setenv("HOUBA_REGISTRIES", '{"eu": {"host": "h", "username": "robot"}}')
    with pytest.raises(ValidationError):
        Settings()


def test_resolve_registry_by_name() -> None:
    roster = {"eu": RegistryConfig(host="a"), "us": RegistryConfig(host="b")}
    name, cfg = resolve_registry("us", roster)
    assert name == "us"
    assert cfg.host == "b"


def test_resolve_registry_unknown_name_raises() -> None:
    with pytest.raises(ConfigError, match="unknown registry"):
        resolve_registry("zz", {"eu": RegistryConfig(host="a")})


def test_resolve_registry_omitted_with_single_uses_it() -> None:
    roster = {"only": RegistryConfig(host="a")}
    name, cfg = resolve_registry(None, roster)
    assert name == "only"
    assert cfg.host == "a"


def test_resolve_registry_omitted_with_multiple_raises() -> None:
    roster = {"eu": RegistryConfig(host="a"), "us": RegistryConfig(host="b")}
    with pytest.raises(ConfigError, match="specify one"):
        resolve_registry(None, roster)


def test_resolve_registry_omitted_with_empty_raises() -> None:
    with pytest.raises(ConfigError, match="no registries"):
        resolve_registry(None, {})
