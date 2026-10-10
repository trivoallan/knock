"""`knock promote`: place the staged rebuilds a filtered file still names.

The second half of the staging seam (see `knock.domain.gate`). `reconcile --apply-plan
--stage-to` held each rebuilt image in a staging registry and listed it; an orchestrator
evaluated the staged digests and removed the entries it refused. This places the rest.

The file is edited outside knock, and this command writes to the destination and signs. So
the file says WHETHER an image is placed, never where or what: the destination comes from the
policy, the staged location from the roster, the identity from the image's stamp, and the tag
is written only once the evidence is found at the destination.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from knock.config import RegistryConfig, match_registry_by_host, resolve_registry
from knock.domain.attestation import COSIGN_ATTESTATION_ARTIFACT_TYPE, PREDICATE_TYPE
from knock.domain.expand import expand_import
from knock.domain.gate import StagedEntry, StagedRebuilds, staged_repository
from knock.domain.mirror_policy import MirrorPolicy, RegistrySource
from knock.domain.policy_merge import resolve_imports
from knock.domain.sbom import media_type_for
from knock.errors import (
    ConfigError,
    PromotionRefusedError,
    StagedDigestMismatchError,
    exit_code_for,
)
from knock.ports.attestor import AttestorPort
from knock.ports.registry import RegistryPort
from knock.ports.reporter import ErrorInfo, OperationEvent, OperationKind, Reporter
from knock.use_cases.registry_session import ensure_registry_session
from knock.use_cases.report import (
    Operation,
    PolicyReport,
    RunReport,
    RunStatus,
    TargetReport,
    VariantReport,
    counts_of,
    merge_counts,
    node_status,
)

_BASE_DIGEST = "org.opencontainers.image.base.digest"


@dataclass(frozen=True)
class _Trusted:
    """What promote re-derived for an entry from its own sources, before touching anything."""

    policy: MirrorPolicy
    dest_cfg: RegistryConfig
    stage_cfg: RegistryConfig


def _refuse(entry: StagedEntry, why: str) -> PromotionRefusedError:
    return PromotionRefusedError(f"{entry.destination}:{entry.tag}: {why}")


def _trust(
    entry: StagedEntry, policies: dict[str, MirrorPolicy], roster: dict[str, RegistryConfig]
) -> _Trusted:
    """Check everything that needs no registry read. Raises before anything is copied."""
    policy = policies.get(entry.policy)
    if policy is None or not isinstance(policy.spec.source, RegistrySource):
        raise _refuse(entry, f"no policy named {entry.policy!r} with a registry source")
    resolved = next((r for r in resolve_imports(policy.spec) if r.name == entry.import_name), None)
    if resolved is None:
        raise _refuse(entry, f"policy {entry.policy!r} has no import {entry.import_name!r}")

    dest_cfg: RegistryConfig | None = None
    for dest in resolved.destinations or []:
        _name, cfg = resolve_registry(dest.registry, roster)
        if f"{cfg.host}/{dest.project}/{dest.repository}" == entry.destination:
            dest_cfg = cfg
    if dest_cfg is None:
        raise _refuse(entry, f"import {entry.import_name!r} does not declare this destination")

    # The staged location is derived, not read: the destination, under a roster registry.
    match = match_registry_by_host(entry.staged, roster)
    if match is None:
        raise _refuse(entry, f"{entry.staged!r} is not in a configured registry")
    stage_cfg = match[1]
    expected = staged_repository(
        entry.destination, destination_host=dest_cfg.host, staging_host=stage_cfg.host
    )
    if entry.staged != expected or entry.staged == entry.destination:
        raise _refuse(entry, f"{entry.staged!r} is not the staging location of this destination")

    # Expanding the import over this one tag says whether the import selects it, and which
    # aliases the policy lets it carry.
    expanded = expand_import(resolved, [entry.source_tag])
    variant = next((v for v in expanded.variants if v.name == entry.variant), None)
    if variant is None or entry.source_tag not in variant.tags:
        raise _refuse(entry, f"import {entry.import_name!r} does not select {entry.source_tag!r}")
    if entry.tag != entry.source_tag + variant.suffix:
        raise _refuse(entry, f"variant {entry.variant!r} does not produce this tag")
    declared = {alias + variant.suffix for alias in variant.aliases}
    for alias in entry.aliases:
        if alias not in declared:
            raise _refuse(entry, f"alias {alias!r} is not declared for this tag")
    return _Trusted(policy=policy, dest_cfg=dest_cfg, stage_cfg=stage_cfg)


def promote_staged(
    staged: StagedRebuilds,
    policies: list[MirrorPolicy],
    *,
    registry: RegistryPort,
    roster: dict[str, RegistryConfig],
    label_prefix: str,
    sbom_formats: list[str],
    attestor: AttestorPort | None,
    reporter: Reporter,
    max_concurrency: int = 1,
) -> RunReport:
    by_name = {p.metadata.name: p for p in policies}
    for entry in staged.entries:
        named = by_name.get(entry.policy)
        if named is not None and named.spec.admit and attestor is None:
            # Placing an admitted image unsigned would be a silent gap: refuse up front.
            raise ConfigError(
                f"policy {entry.policy!r} is admit: true but no KNOCK_ATTEST_SIGNER is "
                "configured to sign its images"
            )
    logged_in: set[str] = set()

    def emit(entry: StagedEntry, op: Operation) -> None:
        ev = OperationEvent(
            policy=entry.policy,
            dest_repo=entry.destination,
            variant=entry.variant,
            kind=op.kind,
            out_tag=op.out_tag,
            src_tag=op.src_tag,
            digest=op.digest,
            applied=op.applied,
            out_digest=op.out_digest,
        )
        if op.error is None:
            reporter.operation_applied(ev)
        else:
            reporter.operation_failed(ev, op.error)

    def place(entry: StagedEntry) -> list[Operation]:
        kind: OperationKind = "imported" if entry.kind == "import" else "updated"
        digest = entry.staged_digest
        dest_by_digest = f"{entry.destination}@{digest}"
        dest_tag = f"{entry.destination}:{entry.tag}"
        ops: list[Operation] = []
        try:
            trusted = _trust(entry, by_name, roster)
            ensure_registry_session(registry, trusted.stage_cfg, logged_in)
            ensure_registry_session(registry, trusted.dest_cfg, logged_in)

            held = registry.inspect(f"{entry.staged}:{entry.tag}")
            if held.digest != digest:
                raise StagedDigestMismatchError(
                    f"{entry.staged}:{entry.tag} resolves to {held.digest}, "
                    f"not to the evaluated {digest}"
                )
            stamp = held.annotations
            expected = {_BASE_DIGEST: entry.source_digest}
            if label_prefix:
                expected |= {
                    f"{label_prefix}.policy": entry.policy,
                    f"{label_prefix}.import": entry.import_name,
                    f"{label_prefix}.variant": entry.variant,
                }
            for key, want in expected.items():
                if stamp.get(key) != want:
                    raise _refuse(
                        entry,
                        f"the staged image's stamp says {key}={stamp.get(key)!r}, not {want!r}",
                    )

            already = (
                entry.tag in registry.list_tags(entry.destination)
                and registry.inspect(dest_tag).digest == digest
            )
            if already:
                # A second run on the same file: the judged digest is in place. Finish
                # what an interrupted run may have left (signature, aliases), no more.
                kind = "skipped"
            else:
                registry.copy(f"{entry.staged}@{digest}", dest_by_digest, referrers=True)
                # A copy that exits 0 does not prove the evidence arrived: registries and
                # tools differ in how they store referrers. Look, then write the tag.
                if registry.inspect(dest_by_digest).digest != digest:
                    raise StagedDigestMismatchError(
                        f"{dest_by_digest} did not receive the evaluated digest"
                    )
                present = {r.artifact_type for r in registry.list_referrers(dest_by_digest)}
                missing = [f for f in sbom_formats if media_type_for(f) not in present]
                if missing:
                    raise _refuse(entry, f"the SBOM ({', '.join(missing)}) did not arrive")
                if attestor is not None and (
                    COSIGN_ATTESTATION_ARTIFACT_TYPE not in present
                    or not attestor.has_attestation(dest_by_digest, PREDICATE_TYPE)
                ):
                    raise _refuse(entry, "the signed attestation did not arrive or does not verify")
                registry.copy(dest_by_digest, dest_tag)
            # Admission is the last act on the image, as in reconcile.
            if (
                trusted.policy.spec.admit
                and attestor is not None
                and not attestor.verify_signature(dest_by_digest)
            ):
                attestor.sign(dest_by_digest)
            ops.append(
                Operation(
                    kind=kind,
                    out_tag=entry.tag,
                    src_tag=entry.source_tag,
                    digest=entry.source_digest,
                    applied=kind != "skipped",
                    out_digest=digest,
                )
            )
        except Exception as exc:
            info = ErrorInfo(
                type=type(exc).__name__, message=str(exc), exit_code=exit_code_for(exc)
            )
            ops.append(
                Operation(
                    kind=kind,
                    out_tag=entry.tag,
                    src_tag=entry.source_tag,
                    digest=entry.source_digest,
                    applied=False,
                    error=info,
                )
            )
            emit(entry, ops[-1])
            return ops
        emit(entry, ops[-1])
        # The aliases reconcile resolved onto this tag, replayed: promote computes none.
        for alias in entry.aliases:
            try:
                registry.copy(dest_tag, f"{entry.destination}:{alias}")
                op = Operation(
                    kind="aliased", out_tag=alias, src_tag=entry.tag, digest=None, applied=True
                )
            except Exception as exc:
                op = Operation(
                    kind="aliased",
                    out_tag=alias,
                    src_tag=entry.tag,
                    digest=None,
                    applied=False,
                    error=ErrorInfo(
                        type=type(exc).__name__, message=str(exc), exit_code=exit_code_for(exc)
                    ),
                )
            ops.append(op)
            emit(entry, op)
        return ops

    reporter.run_started(len({e.policy for e in staged.entries}), mode="apply")
    results = _run(staged.entries, place, max_concurrency)

    # Reassemble policy → destination → variant, in the file's order.
    tree: dict[str, dict[str, dict[str, list[Operation]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for entry, ops in zip(staged.entries, results, strict=True):
        tree[entry.policy][entry.destination][entry.variant].extend(ops)
    policy_reports: list[PolicyReport] = []
    for name, targets in tree.items():
        target_reports = [
            TargetReport(
                dest_repo=dest,
                status=node_status([op for ops in variants.values() for op in ops]),
                variants=[
                    VariantReport(
                        name=variant,
                        suffix="",
                        status=node_status(ops),
                        totals=counts_of(ops),
                        operations=ops,
                    )
                    for variant, ops in variants.items()
                ],
                operations=[],
                totals=counts_of([op for ops in variants.values() for op in ops]),
            )
            for dest, variants in targets.items()
        ]
        totals = merge_counts([t.totals for t in target_reports])
        policy = by_name.get(name)
        source = (
            f"{policy.spec.source.registry}/{policy.spec.source.repository}"
            if policy is not None and isinstance(policy.spec.source, RegistrySource)
            else ""
        )
        reporter.policy_completed(name, totals)
        policy_reports.append(
            PolicyReport(
                name=name,
                source=source,
                status=node_status(
                    [op for t in target_reports for v in t.variants for op in v.operations]
                ),
                totals=totals,
                targets=target_reports,
            )
        )

    statuses = [p.status for p in policy_reports]
    status: RunStatus
    if all(s == "ok" for s in statuses):
        status = "ok"
    elif all(s == "failed" for s in statuses):
        status = "failed"
    else:
        status = "partial"
    report = RunReport(
        mode="apply",
        status=status,
        totals=merge_counts([p.totals for p in policy_reports]),
        policies=policy_reports,
    )
    reporter.run_completed(report)
    return report


def _run(
    entries: list[StagedEntry],
    fn: Callable[[StagedEntry], list[Operation]],
    max_concurrency: int,
) -> list[list[Operation]]:
    """Run `fn` over the entries, results in input order (cf. reconcile's `_run_stage`)."""
    if max_concurrency <= 1:
        return [fn(e) for e in entries]
    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        return [f.result() for f in [executor.submit(fn, e) for e in entries]]
