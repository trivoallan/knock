"""Reconcile use case: orchestrate selection → expand → reconcile → apply against
real registries via the RegistryPort (copy path). Depends only on ports.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from houba.config import (
    CACertSource,
    PackageMirror,
    RegistryConfig,
    resolve_ca_certs,
    resolve_mirror,
    resolve_registry,
)
from houba.domain.collision import AliasTarget, detect_alias_collisions
from houba.domain.expand import ExpandedImport, expand_import
from houba.domain.mirror_policy import MirrorPolicy, TransformStep
from houba.domain.policy_merge import resolve_imports
from houba.domain.reconcile import MirrorArtifact, SourceArtifact, reconcile_import
from houba.domain.stamp import build_stamp_annotations
from houba.domain.transforms.base import ResolvedResource, ResolvedStep, ResourceRef
from houba.domain.transforms.registry import DEFAULT_REGISTRY
from houba.domain.transforms.render import render, transform_version, validate_transform_steps
from houba.errors import ConfigError, InternalError
from houba.ports.image_builder import BuildRequest, ImageBuilderPort
from houba.ports.registry import ImageInfo, RegistryPort

BASE_DIGEST_KEY = "org.opencontainers.image.base.digest"


def to_source_artifact(info: ImageInfo, *, now: datetime) -> SourceArtifact:
    # Unknown created time → use `now` (conservative: treated as just-pushed, so the
    # 7-day stability window skips an update rather than churning on unknown freshness).
    return SourceArtifact(digest=info.digest, pushed_at=info.created or now)


def to_mirror_artifact(
    info: ImageInfo, *, transform_version_key: str | None = None
) -> MirrorArtifact | None:
    base = info.annotations.get(BASE_DIGEST_KEY)
    if base is None:
        return None
    tv = info.annotations.get(transform_version_key) if transform_version_key else None
    return MirrorArtifact(base_digest=base, transform_version=tv)


def _read_cert_file(path: str) -> str:
    try:
        return Path(path).read_text()
    except OSError as e:
        raise ConfigError(f"cannot read CA cert file {path!r}: {e}") from e


@dataclass(frozen=True)
class _ResolvedTransform:
    resolved_steps: list[ResolvedStep]
    version: str


def _resolve_ref(
    ref: ResourceRef,
    ca_certs: dict[str, CACertSource],
    package_mirrors: dict[str, PackageMirror],
) -> ResolvedResource:
    if ref.kind == "caCert":
        ((name, src),) = resolve_ca_certs([ref.name], ca_certs)
        if src.pem is not None:
            content = src.pem
        else:
            # path is guaranteed non-None when pem is None by CACertSource._exactly_one
            assert src.path is not None
            content = _read_cert_file(src.path)
        return ResolvedResource(kind="caCert", name=name, filename=f"{name}.crt", content=content)
    if ref.kind == "packageMirror":
        m = resolve_mirror(ref.name, package_mirrors)
        return ResolvedResource(kind="packageMirror", name=ref.name, apt=m.apt, apk=m.apk)
    raise InternalError(f"no resolver for resource kind {ref.kind!r}")


def _resolve_transform(
    steps: list[TransformStep],
    ca_certs: dict[str, CACertSource],
    package_mirrors: dict[str, PackageMirror],
) -> _ResolvedTransform:
    resolved_steps: list[ResolvedStep] = []
    for step in steps:
        compiler = DEFAULT_REGISTRY.get(step.name)
        params = compiler.params_model.model_validate(step.params)
        resources = tuple(
            _resolve_ref(ref, ca_certs, package_mirrors) for ref in compiler.resource_refs(params)
        )
        resolved_steps.append(ResolvedStep(step=step, resources=resources))
    version = transform_version(resolved_steps)
    return _ResolvedTransform(resolved_steps=resolved_steps, version=version)


def _build_variant(
    *,
    builder: ImageBuilderPort,
    source_ref: str,
    dest_ref: str,
    resolved: _ResolvedTransform,
    platform: str,
    work_dir: Path | None = None,
) -> None:
    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="houba-build-", dir=work_dir) as tmp:
        ctx = Path(tmp)
        rendered = render(resolved.resolved_steps, source_ref=source_ref)
        for cf in rendered.context_files:
            (ctx / cf.path).write_text(cf.content)
        df_path = ctx / "Dockerfile"
        df_path.write_text(rendered.dockerfile)
        builder.build_and_push(
            BuildRequest(
                dockerfile_path=df_path, context_dir=ctx, image_ref=dest_ref, platform=platform
            )
        )


@dataclass(frozen=True)
class RunSummary:
    imported: int
    updated: int
    deleted: int
    aliased: int


@dataclass(frozen=True)
class _Plan:
    policy: MirrorPolicy
    expanded: ExpandedImport
    dest_repo: str
    config: RegistryConfig
    transforms: dict[str, _ResolvedTransform]  # variant name → resolved transform


@dataclass
class _Counts:
    imported: int = 0
    updated: int = 0
    deleted: int = 0
    aliased: int = 0


def _source_repo(policy: MirrorPolicy) -> str:
    s = policy.spec.source
    return f"{s.registry}/{s.repository}"


def reconcile_policies(
    policies: list[MirrorPolicy],
    *,
    registry: RegistryPort,
    builder: ImageBuilderPort,
    roster: dict[str, RegistryConfig],
    ca_certs: dict[str, CACertSource],
    package_mirrors: dict[str, PackageMirror],
    build_platform: str,
    now: datetime,
    label_prefix: str,
    dry_run_tags: bool,
    dry_run_deletions: bool,
    work_dir: Path | None = None,
) -> RunSummary:
    # --- Plan phase: expand everything, resolve destinations, collision-check. ---
    plans: list[_Plan] = []
    alias_entries: list[AliasTarget] = []
    for policy in policies:
        src_tags = registry.list_tags(_source_repo(policy))
        for resolved in resolve_imports(policy.spec):
            expanded = expand_import(resolved, src_tags)
            for v in expanded.variants:
                validate_transform_steps(v.transform)
            # Resolve transforms (unknown cert/mirror names AND unreadable cert files)
            # during planning so all config errors surface before ANY mutation.
            transforms = {
                v.name: _resolve_transform(v.transform, ca_certs, package_mirrors)
                for v in expanded.variants
                if v.transform
            }
            for dest in resolved.destinations or []:
                _name, cfg = resolve_registry(dest.registry, roster)
                dest_repo = f"{cfg.host}/{dest.project}/{dest.repository}"
                plans.append(
                    _Plan(
                        policy=policy,
                        expanded=expanded,
                        dest_repo=dest_repo,
                        config=cfg,
                        transforms=transforms,
                    )
                )
                for variant in expanded.variants:
                    for alias_name, target in variant.aliases.items():
                        alias_entries.append(
                            AliasTarget(
                                dest_repo=dest_repo,
                                alias=alias_name + variant.suffix,
                                target=target + variant.suffix,
                            )
                        )
    detect_alias_collisions(alias_entries)  # fail fast before ANY mutation

    # --- Apply phase. ---
    counts = _Counts()
    logged_in: set[str] = set()
    for plan in plans:
        cfg = plan.config
        if cfg.host not in logged_in:
            if cfg.username is not None and cfg.password is not None:
                registry.login(
                    cfg.host,
                    username=cfg.username,
                    password=cfg.password.get_secret_value(),
                    tls_verify=cfg.tls_verify,
                )
            logged_in.add(cfg.host)

        src_repo = _source_repo(plan.policy)
        # Every variant shares the same selected source tags (the suffix differentiates
        # the output), but union defensively so a missing source entry can't arise.
        selected = sorted({tag for v in plan.expanded.variants for tag in v.tags})
        source: dict[str, SourceArtifact] = {
            tag: to_source_artifact(registry.inspect(f"{src_repo}:{tag}"), now=now)
            for tag in selected
        }
        tv_key = f"{label_prefix}.transform.version" if label_prefix else None
        resolved_by_variant = plan.transforms
        transform_versions: dict[str, str | None] = {
            name: rt.version for name, rt in plan.transforms.items()
        }

        mirror: dict[str, MirrorArtifact] = {}
        for out_tag in registry.list_tags(plan.dest_repo):
            ma = to_mirror_artifact(
                registry.inspect(f"{plan.dest_repo}:{out_tag}"), transform_version_key=tv_key
            )
            if ma is not None:
                mirror[out_tag] = ma

        result = reconcile_import(
            plan.expanded, source, mirror, now, transform_versions=transform_versions
        )

        for vr, vplan in zip(result.variants, plan.expanded.variants, strict=True):
            out_to_src: dict[str, str] = {t + vplan.suffix: t for t in vplan.tags}
            for out_tag in [*vr.to_import, *vr.to_update]:
                src_tag = out_to_src[out_tag]
                if out_tag in vr.to_import:
                    counts.imported += 1
                else:
                    counts.updated += 1
                stamp = build_stamp_annotations(
                    prefix=label_prefix,
                    source_registry=plan.policy.spec.source.registry,
                    source_repository=plan.policy.spec.source.repository,
                    source_tag=src_tag,
                    source_digest=source[src_tag].digest,
                    created=now,
                    team=(plan.policy.metadata.labels or {}).get("team"),
                    artifact_type=plan.policy.spec.artifact_type.value,
                    policy=plan.policy.metadata.name,
                    import_name=plan.expanded.name,
                    variant=vr.variant,
                    transform_steps=[s.name for s in vplan.transform] or None,
                    transform_version_value=transform_versions.get(vplan.name),
                )
                if not dry_run_tags:
                    if vplan.transform:
                        _build_variant(
                            builder=builder,
                            source_ref=f"{src_repo}@{source[src_tag].digest}",
                            dest_ref=f"{plan.dest_repo}:{out_tag}",
                            resolved=resolved_by_variant[vplan.name],
                            platform=build_platform,
                            work_dir=work_dir,
                        )
                    else:
                        registry.copy(f"{src_repo}:{src_tag}", f"{plan.dest_repo}:{out_tag}")
                    registry.annotate(f"{plan.dest_repo}:{out_tag}", stamp)
            for alias_name, target in vr.aliases.items():
                counts.aliased += 1
                if not dry_run_tags:
                    registry.copy(f"{plan.dest_repo}:{target}", f"{plan.dest_repo}:{alias_name}")

        for out_tag in result.to_delete:
            counts.deleted += 1
            if not dry_run_deletions:
                registry.delete_tag(f"{plan.dest_repo}:{out_tag}")

    return RunSummary(
        imported=counts.imported,
        updated=counts.updated,
        deleted=counts.deleted,
        aliased=counts.aliased,
    )
