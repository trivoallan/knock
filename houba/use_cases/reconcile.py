"""Reconcile use case: orchestrate selection → expand → reconcile → apply against
real registries. Tags are mirrored by copy, or rebuilt through a hardening
transform, then stamped. Returns a structured RunReport and emits in-flight
events through the Reporter port. Depends only on ports.
"""

from __future__ import annotations

import tempfile
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from houba.config import (
    CACertSource,
    PackageMirror,
    RegistryConfig,
    resolve_ca_certs,
    resolve_mirror,
    resolve_registry,
)
from houba.domain.collision import (
    AliasTarget,
    detect_alias_collisions,
    detect_dest_repo_collisions,
)
from houba.domain.expand import ExpandedImport, VariantPlan, expand_import
from houba.domain.mirror_policy import MirrorPolicy, TransformStep
from houba.domain.policy_merge import resolve_imports
from houba.domain.reconcile import (
    MirrorArtifact,
    SourceArtifact,
    reconcile_import,
)
from houba.domain.sharding import owns
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


def _resolved_dest_repos(policy: MirrorPolicy, roster: dict[str, RegistryConfig]) -> list[str]:
    """Every destination repo a policy writes to, resolved against the roster.
    Pure: uses resolve_imports + resolve_registry only (no expand, no registry calls)."""
    repos: list[str] = []
    for resolved in resolve_imports(policy.spec):
        for dest in resolved.destinations or []:
            _name, cfg = resolve_registry(dest.registry, roster)
            repos.append(f"{cfg.host}/{dest.project}/{dest.repository}")
    return repos


def _run_stage[T](
    items: list[T], fn: Callable[[T], Operation], *, executor: ThreadPoolExecutor | None
) -> list[Operation]:
    """Run `fn` over `items`. Results preserve input order regardless of completion
    order (so the assembled report is deterministic). Sequential when executor is None;
    the `.result()` join is also the barrier that ends the stage."""
    if executor is None:
        return [fn(it) for it in items]
    futures = [executor.submit(fn, it) for it in items]
    return [f.result() for f in futures]


def _node_status(operations: list[Operation]) -> Literal["ok", "partial", "failed"]:
    if all(op.error is None for op in operations):
        return "ok"
    return "partial" if any(op.error is None for op in operations) else "failed"


@dataclass(frozen=True)
class _ImportWork:
    variant: str
    vplan: VariantPlan
    out_tag: str
    src_tag: str
    kind: OperationKind


@dataclass(frozen=True)
class _AliasWork:
    variant: str
    alias: str
    target: str


@dataclass(frozen=True)
class _DeleteWork:
    out_tag: str


def _counts_of(operations: list[Operation]) -> Counts:
    def n(kind: str) -> int:
        return sum(1 for op in operations if op.error is None and op.kind == kind)

    return Counts(
        imported=n("imported"),
        updated=n("updated"),
        deleted=n("deleted"),
        aliased=n("aliased"),
        skipped=n("skipped"),
        failed=sum(1 for op in operations if op.error is not None),
    )


def _merge_counts(parts: list[Counts]) -> Counts:
    return Counts(
        imported=sum(c.imported for c in parts),
        updated=sum(c.updated for c in parts),
        deleted=sum(c.deleted for c in parts),
        aliased=sum(c.aliased for c in parts),
        skipped=sum(c.skipped for c in parts),
        failed=sum(c.failed for c in parts),
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
    executor: ThreadPoolExecutor | None,
) -> TargetReport:
    src_repo = _source_repo(plan.policy)
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

    def emit_applied(op: Operation, variant: str) -> None:
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

    def emit_failed(op: Operation, variant: str, error: ErrorInfo) -> None:
        reporter.operation_failed(
            OperationEvent(
                policy=policy_name,
                dest_repo=plan.dest_repo,
                variant=variant,
                kind=op.kind,
                out_tag=op.out_tag,
                src_tag=op.src_tag,
                digest=op.digest,
                applied=False,
            ),
            error,
        )

    def _do_import(w: _ImportWork) -> Operation:
        try:
            if not dry_run_tags:
                if w.vplan.transform:
                    _build_variant(
                        builder=builder,
                        source_ref=f"{src_repo}@{source[w.src_tag].digest}",
                        dest_ref=f"{plan.dest_repo}:{w.out_tag}",
                        resolved=plan.transforms[w.vplan.name],
                        platform=build_platform,
                        work_dir=work_dir,
                    )
                else:
                    registry.copy(f"{src_repo}:{w.src_tag}", f"{plan.dest_repo}:{w.out_tag}")
                registry.annotate(
                    f"{plan.dest_repo}:{w.out_tag}",
                    build_stamp_annotations(
                        prefix=label_prefix,
                        source_registry=plan.policy.spec.source.registry,
                        source_repository=plan.policy.spec.source.repository,
                        source_tag=w.src_tag,
                        source_digest=source[w.src_tag].digest,
                        created=now,
                        team=(plan.policy.metadata.labels or {}).get("team"),
                        artifact_type=plan.policy.spec.artifact_type.value,
                        policy=plan.policy.metadata.name,
                        import_name=plan.expanded.name,
                        variant=w.variant,
                        transform_steps=[s.name for s in w.vplan.transform] or None,
                        transform_version_value=transform_versions.get(w.vplan.name),
                    ),
                )
            op = Operation(
                kind=w.kind,
                out_tag=w.out_tag,
                src_tag=w.src_tag,
                digest=source[w.src_tag].digest,
                applied=not dry_run_tags,
            )
            emit_applied(op, w.variant)
            return op
        except Exception as exc:
            info = ErrorInfo(
                type=type(exc).__name__, message=str(exc), exit_code=exit_code_for(exc)
            )
            op = Operation(
                kind=w.kind,
                out_tag=w.out_tag,
                src_tag=w.src_tag,
                digest=source[w.src_tag].digest,
                applied=False,
                error=info,
            )
            emit_failed(op, w.variant, info)
            return op

    def _do_alias(w: _AliasWork) -> Operation:
        try:
            if not dry_run_tags:
                registry.copy(f"{plan.dest_repo}:{w.target}", f"{plan.dest_repo}:{w.alias}")
            op = Operation(
                kind="aliased",
                out_tag=w.alias,
                src_tag=w.target,
                digest=None,
                applied=not dry_run_tags,
            )
            emit_applied(op, w.variant)
            return op
        except Exception as exc:
            info = ErrorInfo(
                type=type(exc).__name__, message=str(exc), exit_code=exit_code_for(exc)
            )
            op = Operation(
                kind="aliased",
                out_tag=w.alias,
                src_tag=w.target,
                digest=None,
                applied=False,
                error=info,
            )
            emit_failed(op, w.variant, info)
            return op

    def _do_delete(w: _DeleteWork) -> Operation:
        try:
            if not dry_run_deletions:
                registry.delete_tag(f"{plan.dest_repo}:{w.out_tag}")
            op = Operation(
                kind="deleted",
                out_tag=w.out_tag,
                src_tag=None,
                digest=None,
                applied=not dry_run_deletions,
            )
            emit_applied(op, "")
            return op
        except Exception as exc:
            info = ErrorInfo(
                type=type(exc).__name__, message=str(exc), exit_code=exit_code_for(exc)
            )
            op = Operation(
                kind="deleted",
                out_tag=w.out_tag,
                src_tag=None,
                digest=None,
                applied=False,
                error=info,
            )
            emit_failed(op, "", info)
            return op

    # Stage 1: imports/updates, all variants flattened, input order preserved.
    import_items: list[_ImportWork] = []
    for vr, vplan in zip(result.variants, plan.expanded.variants, strict=True):
        out_to_src = {t + vplan.suffix: t for t in vplan.tags}
        for out_tag in [*vr.to_import, *vr.to_update]:
            kind: OperationKind = "imported" if out_tag in vr.to_import else "updated"
            import_items.append(
                _ImportWork(
                    variant=vr.variant,
                    vplan=vplan,
                    out_tag=out_tag,
                    src_tag=out_to_src[out_tag],
                    kind=kind,
                )
            )
    import_ops = _run_stage(import_items, _do_import, executor=executor)

    # Barrier. Stage 2: aliases (depend on the imported targets).
    alias_items: list[_AliasWork] = []
    for vr in result.variants:
        for alias_name, target in vr.aliases.items():
            alias_items.append(_AliasWork(variant=vr.variant, alias=alias_name, target=target))
    alias_ops = _run_stage(alias_items, _do_alias, executor=executor)

    # Barrier. Stage 3: deletions (target-level).
    delete_items = [_DeleteWork(out_tag=t) for t in result.to_delete]
    delete_ops = _run_stage(delete_items, _do_delete, executor=executor)

    # Reassemble per-variant reports, preserving input order.
    imports_by_variant: dict[str, list[Operation]] = defaultdict(list)
    for it, op in zip(import_items, import_ops, strict=True):
        imports_by_variant[it.variant].append(op)
    aliases_by_variant: dict[str, list[Operation]] = defaultdict(list)
    for ait, op in zip(alias_items, alias_ops, strict=True):
        aliases_by_variant[ait.variant].append(op)

    variant_reports: list[VariantReport] = []
    for vr, vplan in zip(result.variants, plan.expanded.variants, strict=True):
        changed = set(vr.to_import) | set(vr.to_update)
        ops: list[Operation] = list(imports_by_variant[vr.variant])
        for tag in vplan.tags:
            out_tag = tag + vplan.suffix
            if out_tag not in changed:
                sop = Operation(
                    kind="skipped",
                    out_tag=out_tag,
                    src_tag=tag,
                    digest=source[tag].digest,
                    applied=False,
                )
                ops.append(sop)
                emit_applied(sop, vr.variant)
        ops.extend(aliases_by_variant[vr.variant])
        variant_reports.append(
            VariantReport(
                name=vr.variant,
                suffix=vplan.suffix,
                status=_node_status(ops),
                totals=_counts_of(ops),
                operations=ops,
            )
        )

    target_ops_all = [op for v in variant_reports for op in v.operations] + delete_ops
    target_totals = _merge_counts([v.totals for v in variant_reports] + [_counts_of(delete_ops)])
    return TargetReport(
        dest_repo=plan.dest_repo,
        status=_node_status(target_ops_all),
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
    max_concurrency: int = 1,
    shard_index: int = 0,
    shard_count: int = 1,
) -> RunReport:
    mode: RunMode = "dry-run" if (dry_run_tags or dry_run_deletions) else "apply"

    # --- Ownership invariant over ALL policies (pure, no I/O), then shard filter. ---
    # Every pod sees the full policy set (git-synced) and enforces one-owner-per-repo
    # identically; it then applies only the policies it owns. shard_count == 1 ⇒ all.
    owners = [
        (repo, policy.metadata.name)
        for policy in policies
        for repo in _resolved_dest_repos(policy, roster)
    ]
    detect_dest_repo_collisions(owners)
    policies = [
        p
        for p in policies
        if owns(p.metadata.name, shard_index=shard_index, shard_count=shard_count)
    ]

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
    with ExitStack() as stack:
        executor: ThreadPoolExecutor | None = (
            stack.enter_context(ThreadPoolExecutor(max_workers=max_concurrency))
            if max_concurrency > 1
            else None
        )
        for policy, policy_plans in plans_by_policy:
            source_ref = _source_repo(policy)
            reporter.policy_started(policy.metadata.name, source_ref)
            try:
                targets: list[TargetReport] = []
                for plan in policy_plans:
                    cfg = plan.config
                    if cfg.host not in logged_in:
                        registry.configure_registry(
                            cfg.host, tls_verify=cfg.tls_verify, ca_cert=cfg.ca_cert
                        )
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
                            executor=executor,
                        )
                    )
                all_ops = [op for t in targets for v in t.variants for op in v.operations] + [
                    op for t in targets for op in t.operations
                ]
                totals = _merge_counts([t.totals for t in targets])
                reporter.policy_completed(policy.metadata.name, totals)
                policy_reports.append(
                    PolicyReport(
                        name=policy.metadata.name,
                        source=source_ref,
                        status=_node_status(all_ops),
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

    statuses = [p.status for p in policy_reports]
    if all(s == "ok" for s in statuses):
        status: RunStatus = "ok"
    elif all(s == "failed" for s in statuses):
        status = "failed"
    else:
        status = "partial"
    report = RunReport(
        mode=mode,
        status=status,
        totals=_merge_counts([p.totals for p in policy_reports]),
        policies=policy_reports,
    )
    reporter.run_completed(report)
    return report
