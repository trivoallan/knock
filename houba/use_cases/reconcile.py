"""Reconcile use case: orchestrate selection → expand → reconcile → apply against
real registries. Tags are mirrored by copy, or rebuilt through a hardening
transform, then stamped. Returns a structured RunReport and emits in-flight
events through the Reporter port. Depends only on ports.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
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
from houba.domain.expand import ExpandedImport, VariantPlan, expand_import
from houba.domain.mirror_policy import MirrorPolicy, TransformStep
from houba.domain.policy_merge import resolve_imports
from houba.domain.reconcile import (
    MirrorArtifact,
    SourceArtifact,
    VariantReconcile,
    reconcile_import,
)
from houba.domain.stamp import build_stamp_annotations
from houba.domain.transforms.base import ResolvedResource, ResolvedStep, ResourceRef
from houba.domain.transforms.registry import DEFAULT_REGISTRY
from houba.domain.transforms.render import render, transform_version, validate_transform_steps
from houba.errors import ConfigError, InternalError, exit_code_for
from houba.ports.image_builder import BuildRequest, ImageBuilderPort
from houba.ports.registry import ImageInfo, RegistryPort
from houba.ports.reporter import Counts, ErrorInfo, OperationEvent, OperationKind, Reporter
from houba.use_cases.report import (
    Operation,
    PolicyReport,
    RunMode,
    RunReport,
    RunStatus,
    TargetReport,
    VariantReport,
)

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
class _Plan:
    policy: MirrorPolicy
    expanded: ExpandedImport
    dest_repo: str
    config: RegistryConfig
    transforms: dict[str, _ResolvedTransform]  # variant name → resolved transform


def _source_repo(policy: MirrorPolicy) -> str:
    s = policy.spec.source
    return f"{s.registry}/{s.repository}"


def _counts_of(operations: list[Operation]) -> Counts:
    def n(kind: str) -> int:
        return sum(1 for op in operations if op.kind == kind)

    return Counts(
        imported=n("imported"),
        updated=n("updated"),
        deleted=n("deleted"),
        aliased=n("aliased"),
        skipped=n("skipped"),
    )


def _merge_counts(parts: list[Counts]) -> Counts:
    return Counts(
        imported=sum(c.imported for c in parts),
        updated=sum(c.updated for c in parts),
        deleted=sum(c.deleted for c in parts),
        aliased=sum(c.aliased for c in parts),
        skipped=sum(c.skipped for c in parts),
    )


def _apply_variant(
    vr: VariantReconcile,
    vplan: VariantPlan,
    *,
    plan: _Plan,
    registry: RegistryPort,
    builder: ImageBuilderPort,
    source: dict[str, SourceArtifact],
    transform_versions: dict[str, str | None],
    label_prefix: str,
    build_platform: str,
    work_dir: Path | None,
    now: datetime,
    dry_run_tags: bool,
    emit: Callable[[Operation, str], None],
) -> VariantReport:
    src_repo = _source_repo(plan.policy)
    out_to_src = {t + vplan.suffix: t for t in vplan.tags}
    changed = set(vr.to_import) | set(vr.to_update)
    ops: list[Operation] = []
    for out_tag in [*vr.to_import, *vr.to_update]:
        src_tag = out_to_src[out_tag]
        kind: OperationKind = "imported" if out_tag in vr.to_import else "updated"
        if not dry_run_tags:
            if vplan.transform:
                _build_variant(
                    builder=builder,
                    source_ref=f"{src_repo}@{source[src_tag].digest}",
                    dest_ref=f"{plan.dest_repo}:{out_tag}",
                    resolved=plan.transforms[vplan.name],
                    platform=build_platform,
                    work_dir=work_dir,
                )
            else:
                registry.copy(f"{src_repo}:{src_tag}", f"{plan.dest_repo}:{out_tag}")
            registry.annotate(
                f"{plan.dest_repo}:{out_tag}",
                build_stamp_annotations(
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
                ),
            )
        op = Operation(
            kind=kind,
            out_tag=out_tag,
            src_tag=src_tag,
            digest=source[src_tag].digest,
            applied=not dry_run_tags,
        )
        ops.append(op)
        emit(op, vr.variant)
    for tag in vplan.tags:
        out_tag = tag + vplan.suffix
        if out_tag not in changed:
            op = Operation(
                kind="skipped",
                out_tag=out_tag,
                src_tag=tag,
                digest=source[tag].digest,
                applied=False,
            )
            ops.append(op)
            emit(op, vr.variant)
    for alias_name, target in vr.aliases.items():
        if not dry_run_tags:
            registry.copy(f"{plan.dest_repo}:{target}", f"{plan.dest_repo}:{alias_name}")
        op = Operation(
            kind="aliased",
            out_tag=alias_name,
            src_tag=target,
            digest=None,
            applied=not dry_run_tags,
        )
        ops.append(op)
        emit(op, vr.variant)
    return VariantReport(
        name=vr.variant, suffix=vplan.suffix, totals=_counts_of(ops), operations=ops
    )


def _apply_plan(
    plan: _Plan,
    *,
    registry: RegistryPort,
    builder: ImageBuilderPort,
    label_prefix: str,
    build_platform: str,
    work_dir: Path | None,
    now: datetime,
    dry_run_tags: bool,
    dry_run_deletions: bool,
    reporter: Reporter,
    policy_name: str,
) -> TargetReport:
    src_repo = _source_repo(plan.policy)
    # Every variant shares the same selected source tags (the suffix differentiates
    # the output), but union defensively so a missing source entry can't arise.
    selected = sorted({tag for v in plan.expanded.variants for tag in v.tags})
    source: dict[str, SourceArtifact] = {
        tag: to_source_artifact(registry.inspect(f"{src_repo}:{tag}"), now=now) for tag in selected
    }
    tv_key = f"{label_prefix}.transform.version" if label_prefix else None
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

    def emit(op: Operation, variant: str) -> None:
        reporter.operation_applied(
            OperationEvent(
                policy=policy_name,
                dest_repo=plan.dest_repo,
                variant=variant,
                kind=op.kind,
                out_tag=op.out_tag,
                src_tag=op.src_tag,
                digest=op.digest,
                applied=op.applied,
            )
        )

    variant_reports = [
        _apply_variant(
            vr,
            vplan,
            plan=plan,
            registry=registry,
            builder=builder,
            source=source,
            transform_versions=transform_versions,
            label_prefix=label_prefix,
            build_platform=build_platform,
            work_dir=work_dir,
            now=now,
            dry_run_tags=dry_run_tags,
            emit=emit,
        )
        for vr, vplan in zip(result.variants, plan.expanded.variants, strict=True)
    ]

    delete_ops: list[Operation] = []
    for out_tag in result.to_delete:
        if not dry_run_deletions:
            registry.delete_tag(f"{plan.dest_repo}:{out_tag}")
        op = Operation(
            kind="deleted",
            out_tag=out_tag,
            src_tag=None,
            digest=None,
            applied=not dry_run_deletions,
        )
        delete_ops.append(op)
        emit(op, "")  # deletions are target-level, not tied to a variant

    target_totals = _merge_counts([v.totals for v in variant_reports] + [_counts_of(delete_ops)])
    return TargetReport(
        dest_repo=plan.dest_repo,
        variants=variant_reports,
        operations=delete_ops,
        totals=target_totals,
    )


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
    reporter: Reporter,
    work_dir: Path | None = None,
) -> RunReport:
    mode: RunMode = "dry-run" if (dry_run_tags or dry_run_deletions) else "apply"

    # --- Plan phase (fail-fast): expand, resolve destinations + transforms, collision-check.
    # Transform resolution (unknown cert/mirror names, unreadable cert files) surfaces all
    # config errors here, before ANY mutation. ---
    plans_by_policy: list[tuple[MirrorPolicy, list[_Plan]]] = []
    alias_entries: list[AliasTarget] = []
    for policy in policies:
        src_tags = registry.list_tags(_source_repo(policy))
        policy_plans: list[_Plan] = []
        for resolved in resolve_imports(policy.spec):
            expanded = expand_import(resolved, src_tags)
            for v in expanded.variants:
                validate_transform_steps(v.transform)
            transforms = {
                v.name: _resolve_transform(v.transform, ca_certs, package_mirrors)
                for v in expanded.variants
                if v.transform
            }
            for dest in resolved.destinations or []:
                _name, cfg = resolve_registry(dest.registry, roster)
                dest_repo = f"{cfg.host}/{dest.project}/{dest.repository}"
                policy_plans.append(
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
        plans_by_policy.append((policy, policy_plans))
    detect_alias_collisions(alias_entries)  # fail fast before ANY mutation

    # --- Apply phase (isolated per policy). ---
    reporter.run_started(len(plans_by_policy), mode=mode)
    logged_in: set[str] = set()
    policy_reports: list[PolicyReport] = []
    for policy, policy_plans in plans_by_policy:
        source_ref = _source_repo(policy)
        reporter.policy_started(policy.metadata.name, source_ref)
        try:
            targets: list[TargetReport] = []
            for plan in policy_plans:
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
                targets.append(
                    _apply_plan(
                        plan,
                        registry=registry,
                        builder=builder,
                        label_prefix=label_prefix,
                        build_platform=build_platform,
                        work_dir=work_dir,
                        now=now,
                        dry_run_tags=dry_run_tags,
                        dry_run_deletions=dry_run_deletions,
                        reporter=reporter,
                        policy_name=policy.metadata.name,
                    )
                )
            totals = _merge_counts([t.totals for t in targets])
            reporter.policy_completed(policy.metadata.name, totals)
            policy_reports.append(
                PolicyReport(
                    name=policy.metadata.name,
                    source=source_ref,
                    status="ok",
                    error=None,
                    totals=totals,
                    targets=targets,
                )
            )
        except Exception as exc:
            info = ErrorInfo(
                type=type(exc).__name__, message=str(exc), exit_code=exit_code_for(exc)
            )
            reporter.policy_failed(policy.metadata.name, info)
            policy_reports.append(
                PolicyReport(
                    name=policy.metadata.name,
                    source=source_ref,
                    status="failed",
                    error=info,
                    totals=Counts(),
                    targets=[],
                )
            )

    failed = sum(1 for p in policy_reports if p.status == "failed")
    status: RunStatus = (
        "ok" if failed == 0 else ("failed" if failed == len(policy_reports) else "partial")
    )
    report = RunReport(
        mode=mode,
        status=status,
        totals=_merge_counts([p.totals for p in policy_reports]),
        policies=policy_reports,
    )
    reporter.run_completed(report)
    return report
