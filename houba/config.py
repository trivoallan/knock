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
from houba.domain.mirror_policy import Archive
from houba.domain.scan.refs import registry_host
from houba.errors import ConfigError


class RegistryConfig(BaseModel):
    """One real registry behind a logical destination name (host + credentials)."""

    model_config = ConfigDict(extra="forbid")

    host: str = Field(
        description="Registry host, e.g. `harbor.example.com` or `localhost:5001`.",
    )
    username: str | None = Field(
        default=None,
        description="Registry username (must be set together with `password`).",
    )
    password: SecretStr | None = Field(
        default=None,
        description="Registry password (must be set together with `username`).",
    )
    tls_verify: bool = Field(
        default=True,
        description="Set to `false` for plain-HTTP registries; houba then runs "
        "`regctl registry set … --tls disabled` automatically.",
    )
    ca_cert: str | None = Field(
        default=None,
        description="Path to a CA PEM regctl should trust for this registry's TLS "
        "(registries behind an internal CA).",
    )
    deletion_mode: DeletionMode | None = Field(
        default=None,
        description="Destination-level override in the deletion-mode cascade "
        "(policy ← destination ← global).",
    )

    @model_validator(mode="after")
    def _credentials_both_or_neither(self) -> RegistryConfig:
        if (self.username is None) != (self.password is None):
            raise ValueError("registry username and password must be set together")
        return self


class CACertSource(BaseModel):
    """A CA certificate supplied either as a filesystem path or as an inline PEM string."""

    model_config = ConfigDict(extra="forbid")

    path: str | None = Field(
        default=None,
        description="Filesystem path to the CA certificate (exactly one of `path` | `pem`).",
    )
    pem: str | None = Field(
        default=None,
        description="Inline CA certificate PEM string (exactly one of `path` | `pem`).",
    )

    @model_validator(mode="after")
    def _exactly_one(self) -> CACertSource:
        if (self.path is None) == (self.pem is None):
            raise ValueError("a CA cert source needs exactly one of path | pem")
        return self


class PackageMirror(BaseModel):
    """Override URLs for one or more OS package managers during image hardening."""

    model_config = ConfigDict(extra="forbid")

    apt: str | None = Field(
        default=None,
        description="Override URL for the apt package source (at least one of `apt` | `apk`).",
    )
    apk: str | None = Field(
        default=None,
        description="Override URL for the apk package source (at least one of `apt` | `apk`).",
    )

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

    signer: Literal["", "keyless", "kms", "key"] = Field(
        default="",
        description='Signing mode: `""` (off, no attestation) | `keyless` | `kms` | `key`.',
    )
    key_ref: str = Field(
        default="", description="KMS URI (`kms`) or key path (`key`); required for those signers."
    )
    fulcio_url: str = Field(default="", description="Keyless CA URL; blank ⇒ public Fulcio.")
    rekor_url: str = Field(
        default="", description="Transparency-log URL; blank ⇒ no log entry (the air-gapped path)."
    )
    builder_id: str = Field(
        default="", description="URI identifying this houba builder (feeds both predicates)."
    )

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

    label_prefix: str = Field(
        default="io.houba",
        description="Prefix for houba's own provenance annotations; "
        "empty ⇒ no houba labels (OCI-standard keys only).",
    )
    registries: dict[str, RegistryConfig] = Field(
        default_factory=dict,
        description="JSON map of logical registry name → `RegistryConfig`. "
        "At least one is needed to reconcile.",
    )

    log_format: Literal["text", "json"] = Field(
        default="text", description="Log output format: `text` or `json`."
    )
    log_level: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR"] = Field(
        default="INFO", description="Minimum log level."
    )
    dry_run_tags: bool = Field(default=False, description="Skip image copies / pushes.")
    dry_run_deletions: bool = Field(default=False, description="Skip deletions.")
    deletion_mode: DeletionMode = Field(
        default=DeletionMode.purge, description="Global baseline of the deletion-mode cascade."
    )
    retention: Archive | None = Field(
        default=None,
        description="Global tier of the retention cascade (a JSON `Archive`); "
        "unset ⇒ retention off everywhere.",
    )
    work_dir: Path = Field(
        default=Path("/tmp/houba-work"),  # noqa: S108
        description="Scratch directory for build contexts.",
    )

    transform_ca_certs: dict[str, CACertSource] = Field(
        default_factory=dict,
        description="JSON map of name → CA source, resolved by the `injectCA` transform.",
    )
    transform_package_mirrors: dict[str, PackageMirror] = Field(
        default_factory=dict,
        description="JSON map of name → package mirror, resolved by `rewritePackageSources`.",
    )
    build_platform: str = Field(
        default="linux/amd64", description="Platform for the rebuild path (single-platform)."
    )
    max_concurrency: int = Field(
        default=4, ge=1, description="Max parallel tag operations per run (`1` = sequential)."
    )

    # SLSA/in-toto attestation (off by default). Flat HOUBA_ATTEST_* fields keep the
    # single-Settings + single-underscore config invariant (CLAUDE.md); `.attest`
    # groups them into the typed DTO the cosign adapter consumes.
    attest_signer: Literal["", "keyless", "kms", "key"] = Field(
        default="",
        description="Signing mode for SLSA attestations on the rebuild path; empty ⇒ off.",
    )
    attest_key_ref: str = Field(default="", description="KMS URI (`kms`) or key path (`key`).")
    attest_fulcio_url: str = Field(default="", description="Keyless CA URL; blank ⇒ public Fulcio.")
    attest_rekor_url: str = Field(
        default="", description="Transparency-log URL; blank ⇒ no log entry."
    )
    attest_builder_id: str = Field(default="", description="URI identifying this houba builder.")

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
    usage_oracle_cmd: str | None = Field(
        default=None,
        description="Executable speaking the usage-oracle contract; required to run `houba purge`.",
    )
    usage_oracle_timeout: int = Field(
        default=30, ge=1, description="Per-query timeout (seconds) for the usage oracle."
    )
    purge_min_idle_days: int | None = Field(
        default=None,
        ge=1,
        description="Idle window `houba purge` requires before reaping a marked tag.",
    )


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


def match_registry_by_host(
    ref: str, roster: dict[str, RegistryConfig]
) -> tuple[str, RegistryConfig] | None:
    """Find the roster entry whose host serves `ref`, by matching the ref's host.

    Returns the (name, config) pair, or None when the ref carries no host-like
    segment or no roster entry matches — the signal to fall back to ambient
    registry config. Never raises (unlike resolve_registry): a non-match is a
    valid, expected outcome for attach.
    """
    host = registry_host(ref)
    if host is None:
        return None
    for name, cfg in roster.items():
        if cfg.host == host:
            return name, cfg
    return None


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


def settings_json_schema() -> dict[str, Any]:
    """Published JSON Schema for the HOUBA_* environment config (derived, never hand-written).

    The env-var name for each field is its property name upper-cased with the `HOUBA_`
    prefix (e.g. `label_prefix` ⇒ `HOUBA_LABEL_PREFIX`); nested objects (`registries`,
    `transform_ca_certs`, …) are passed as JSON in that single var.
    """
    return Settings.model_json_schema()
