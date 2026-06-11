"""Reconcile use case: orchestrate selection → expand → reconcile → apply against
real registries via the RegistryPort (copy path). Depends only on ports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from houba.config import RegistryConfig, resolve_registry
from houba.domain.collision import AliasTarget, detect_alias_collisions
from houba.domain.expand import ExpandedImport, expand_import
from houba.domain.mirror_policy import MirrorPolicy
from houba.domain.policy_merge import resolve_imports
from houba.domain.reconcile import MirrorArtifact, SourceArtifact, reconcile_import
from houba.domain.stamp import build_stamp_annotations
from houba.ports.registry import ImageInfo, RegistryPort

BASE_DIGEST_KEY = "org.opencontainers.image.base.digest"


def to_source_artifact(info: ImageInfo, *, now: datetime) -> SourceArtifact:
    # Unknown created time → use `now` (conservative: treated as just-pushed, so the
    # 7-day stability window skips an update rather than churning on unknown freshness).
    return SourceArtifact(digest=info.digest, pushed_at=info.created or now)


def to_mirror_artifact(info: ImageInfo) -> MirrorArtifact | None:
    base = info.annotations.get(BASE_DIGEST_KEY)
    if base is None:
        return None
    return MirrorArtifact(base_digest=base)


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
    roster: dict[str, RegistryConfig],
    now: datetime,
    label_prefix: str,
    dry_run_tags: bool,
    dry_run_deletions: bool,
) -> RunSummary:
    # --- Plan phase: expand everything, resolve destinations, collision-check. ---
    plans: list[_Plan] = []
    alias_entries: list[AliasTarget] = []
    for policy in policies:
        src_tags = registry.list_tags(_source_repo(policy))
        for resolved in resolve_imports(policy.spec):
            expanded = expand_import(resolved, src_tags)
            for dest in resolved.destinations or []:
                _name, cfg = resolve_registry(dest.registry, roster)
                dest_repo = f"{cfg.host}/{dest.project}/{dest.repository}"
                plans.append(
                    _Plan(policy=policy, expanded=expanded, dest_repo=dest_repo, config=cfg)
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
        mirror: dict[str, MirrorArtifact] = {}
        for out_tag in registry.list_tags(plan.dest_repo):
            ma = to_mirror_artifact(registry.inspect(f"{plan.dest_repo}:{out_tag}"))
            if ma is not None:
                mirror[out_tag] = ma

        result = reconcile_import(plan.expanded, source, mirror, now)

        for vr, vplan in zip(result.variants, plan.expanded.variants, strict=True):
            out_to_src: dict[str, str] = {t + vplan.suffix: t for t in vplan.tags}
            for out_tag in [*vr.to_import, *vr.to_update]:
                src_tag = out_to_src[out_tag]
                if out_tag in vr.to_import:
                    counts.imported += 1
                else:
                    counts.updated += 1
                if not dry_run_tags:
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
                        ),
                    )
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
