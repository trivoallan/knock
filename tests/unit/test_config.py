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


# ---------------------------------------------------------------------------
# Task 2 — CA cert sources, package mirrors, build_platform
# ---------------------------------------------------------------------------


from houba.config import (  # noqa: E402
    CACertSource,
    PackageMirror,
    resolve_ca_certs,
    resolve_mirror,
)


def test_ca_cert_source_accepts_path_only() -> None:
    assert CACertSource(path="/etc/houba/certs/corp.pem").path == "/etc/houba/certs/corp.pem"


def test_ca_cert_source_accepts_pem_only() -> None:
    assert CACertSource(pem="-----BEGIN CERTIFICATE-----\n...").pem is not None


def test_ca_cert_source_rejects_both_or_neither() -> None:
    with pytest.raises(ValueError, match="exactly one of path"):
        CACertSource(path="/x", pem="y")
    with pytest.raises(ValueError, match="exactly one of path"):
        CACertSource()


def test_package_mirror_requires_at_least_one_manager() -> None:
    assert PackageMirror(apt="https://mirror.corp").apt == "https://mirror.corp"
    with pytest.raises(ValueError, match="at least one of apt"):
        PackageMirror()


def test_rosters_parse_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOUBA_TRANSFORM_CA_CERTS", '{"corp": {"path": "/etc/houba/certs/c.pem"}}')
    monkeypatch.setenv(
        "HOUBA_TRANSFORM_PACKAGE_MIRRORS",
        '{"corp": {"apt": "https://mirror.corp", "apk": "https://mirror.corp"}}',
    )
    s = Settings()
    assert s.transform_ca_certs["corp"].path == "/etc/houba/certs/c.pem"
    assert s.transform_package_mirrors["corp"].apt == "https://mirror.corp"


def test_build_platform_defaults_to_amd64() -> None:
    assert Settings().build_platform == "linux/amd64"


def test_resolve_ca_certs_returns_named_sources() -> None:
    roster = {"corp": CACertSource(pem="PEM")}
    assert resolve_ca_certs(["corp"], roster) == [("corp", CACertSource(pem="PEM"))]


def test_resolve_ca_certs_unknown_name_raises() -> None:
    with pytest.raises(ConfigError, match="unknown CA cert 'nope'"):
        resolve_ca_certs(["nope"], {})


def test_resolve_mirror_unknown_name_raises() -> None:
    with pytest.raises(ConfigError, match="unknown package mirror 'nope'"):
        resolve_mirror("nope", {})


# ---------------------------------------------------------------------------
# Task 1 — RegistryConfig.ca_cert
# ---------------------------------------------------------------------------


def test_registry_config_ca_cert_defaults_none() -> None:
    from houba.config import RegistryConfig

    assert RegistryConfig(host="harbor.corp").ca_cert is None


def test_registry_config_ca_cert_parses_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "HOUBA_REGISTRIES",
        '{"corp": {"host": "harbor.corp", "tls_verify": false,'
        ' "ca_cert": "/etc/houba/registry-ca.pem"}}',
    )
    assert Settings().registries["corp"].ca_cert == "/etc/houba/registry-ca.pem"


# ---------------------------------------------------------------------------
# Task 3 — max_concurrency
# ---------------------------------------------------------------------------


def test_max_concurrency_defaults_to_4() -> None:
    from houba.config import Settings

    assert Settings().max_concurrency == 4


def test_max_concurrency_read_from_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from houba.config import Settings

    monkeypatch.setenv("HOUBA_MAX_CONCURRENCY", "8")
    assert Settings().max_concurrency == 8


def test_max_concurrency_rejects_zero(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import pytest
    from pydantic import ValidationError

    from houba.config import Settings

    monkeypatch.setenv("HOUBA_MAX_CONCURRENCY", "0")
    with pytest.raises(ValidationError):
        Settings()
