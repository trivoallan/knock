"""Read configuration from environment variables.

No other module should read os.environ directly.
See spec §6.1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from houba.domain.deletion_mode import DeletionMode
from houba.errors import ConfigError


class RegistryConfig(BaseModel):
    """One real registry behind a logical destination name (host + credentials)."""

    model_config = ConfigDict(extra="forbid")

    host: str  # registry host, e.g. "harbor.corp.example.com" or "localhost:5000"
    username: str | None = None
    password: SecretStr | None = None
    tls_verify: bool = True
    ca_cert: str | None = None  # path to a CA PEM regctl should trust for this registry's TLS
    deletion_mode: DeletionMode | None = None  # destination-level cascade override

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


class AttestSettings(BaseModel):
    """SLSA/in-toto signing config — the typed view of the flat HOUBA_ATTEST_* vars.

    Off by default: an empty signer => no attestation (mirroring empty
    HOUBA_LABEL_PREFIX => no labels). kms/key require a key reference.
    """

    model_config = ConfigDict(extra="forbid")

    signer: Literal["", "keyless", "kms", "key"] = ""
    key_ref: str = ""  # KMS URI (kms) or key path (key)
    fulcio_url: str = ""  # keyless CA; blank => public Fulcio
    rekor_url: str = ""  # transparency log; blank => no log entry (air-gapped path)
    builder_id: str = ""  # URI identifying this houba builder (feeds both predicates)

    @model_validator(mode="after")
    def _key_required_for_keyed_signers(self) -> AttestSettings:
        if self.signer in ("kms", "key") and not self.key_ref:
            raise ValueError(f"signer {self.signer!r} requires HOUBA_ATTEST_KEY_REF")
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
    deletion_mode: DeletionMode = DeletionMode.purge  # global cascade baseline
    work_dir: Path = Path("/tmp/houba-work")  # noqa: S108

    transform_ca_certs: dict[str, CACertSource] = Field(default_factory=dict)
    transform_package_mirrors: dict[str, PackageMirror] = Field(default_factory=dict)
    build_platform: str = "linux/amd64"
    max_concurrency: int = Field(default=4, ge=1)

    # SLSA/in-toto attestation (off by default). Flat HOUBA_ATTEST_* fields keep the
    # single-Settings + single-underscore config invariant (CLAUDE.md); `.attest`
    # groups them into the typed DTO the cosign adapter consumes.
    attest_signer: Literal["", "keyless", "kms", "key"] = ""
    attest_key_ref: str = ""
    attest_fulcio_url: str = ""
    attest_rekor_url: str = ""
    attest_builder_id: str = ""

    @property
    def attest(self) -> AttestSettings:
        return AttestSettings(
            signer=self.attest_signer,
            key_ref=self.attest_key_ref,
            fulcio_url=self.attest_fulcio_url,
            rekor_url=self.attest_rekor_url,
            builder_id=self.attest_builder_id,
        )

    @model_validator(mode="after")
    def _validate_attest(self) -> Settings:
        # Building the DTO runs AttestSettings' own validation, so a bad
        # HOUBA_ATTEST_* combo surfaces as a ValidationError at Settings() time
        # (mapped to exit 3 in cli/main.py).
        _ = self.attest
        return self

    # houba purge (the reference reaper) — unused by reconcile.
    usage_oracle_cmd: str | None = None
    usage_oracle_timeout: int = Field(default=30, ge=1)
    purge_min_idle_days: int | None = Field(default=None, ge=1)


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


def attest_settings_json_schema() -> dict[str, Any]:
    """Published JSON Schema for the attestation config block (derived, never hand-written)."""
    return AttestSettings.model_json_schema()
