"""`knock lint`: validate a policy tree offline and report every finding (design D1-D9).

Three levels, each a stricter reading of the same tree:

- **N1**: each file loads as a MirrorPolicy, through the loader `reconcile` uses (D1).
- **N2**: pure checks on the loaded policies: every resolved `transform` / `remediate`
  step of each import and variant (D9), destination ownership across policies, and
  alias overlaps between the imports of one policy (D3, D4).
- **N3**: references to the configuration (destination registry, CA certs, package
  mirrors, readable CA files), only when a registry roster is given (D5).

Nothing here calls a registry, git remote or tool; the only I/O is reading the CA files
the configuration names. Findings are data: no `ConfigError` escapes `lint_policies`.

Findings order (deterministic): N1 findings in loader order (paths sorted); then, for
each loaded policy in path order, its N2 step errors, its N2 alias findings and its N3
errors; then the N2 ownership errors, sorted by repository key. Warnings follow the
same order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from knock.config import (
    CACertSource,
    PackageMirror,
    RegistryConfig,
    resolve_ca_certs,
    resolve_mirror,
    resolve_registry,
)
from knock.domain.collision import AliasClaim, find_alias_overlaps
from knock.domain.mirror_policy import Destination, GitSource, MirrorPolicy, TransformStep
from knock.domain.policy_merge import ResolvedImport, resolve_imports
from knock.domain.transforms.base import ResourceRef
from knock.domain.transforms.registry import DEFAULT_REGISTRY
from knock.domain.transforms.render import validate_transform_steps
from knock.domain.variants import expand_variants
from knock.errors import ConfigError, PolicyValidationError
from knock.use_cases.loader import LoadedPolicy, load_policy_files

Level = Literal["N1", "N2", "N3"]


class Finding(BaseModel):
    """One problem in the tree: its level, the file, where in it, and what."""

    level: Level
    path: str = Field(description="Policy file, relative to the linted directory (POSIX).")
    loc: list[str | int] | None = Field(
        default=None, description="Location inside the policy document, when known."
    )
    message: str
    related: list[str] = Field(
        default_factory=list, description="Other files involved (ownership collisions)."
    )


class Skipped(BaseModel):
    """A level that did not run, and why."""

    level: str
    reason: str


class LintReport(BaseModel):
    """The `knock lint` report. Compatibility rule: within one `apiVersion`, only optional
    fields are added; removing, renaming, retyping or changing the meaning of a field bumps it."""

    # Same envelope convention as `CoverageReport` (camelCase on the wire).
    model_config = ConfigDict(populate_by_name=True)

    api_version: Literal["knock.io/v1alpha1"] = Field(
        default="knock.io/v1alpha1", alias="apiVersion"
    )
    kind: Literal["LintReport"] = "LintReport"
    errors: list[Finding]
    warnings: list[Finding]
    skipped: list[Skipped]


def lint_report_json_schema() -> dict[str, Any]:
    """Published JSON Schema for the lint report (derived, never hand-written)."""
    return LintReport.model_json_schema(by_alias=True)


def lint_exit_code(report: LintReport) -> int:
    """0 when the report holds no error, whatever its warnings and skips; else 1 (D8)."""
    return 1 if report.errors else 0


@dataclass
class _PolicyFindings:
    """What one policy contributes, gathered in order, deduplicated by message."""

    path: str
    errors: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)

    def add(self, level: Level, message: str, *, warning: bool = False) -> None:
        target = self.warnings if warning else self.errors
        if any(f.level == level and f.message == message for f in target):
            return
        target.append(Finding(level=level, path=self.path, message=message))


def lint_policies(
    directory: Path,
    *,
    roster: dict[str, RegistryConfig],
    ca_certs: dict[str, CACertSource],
    package_mirrors: dict[str, PackageMirror],
) -> LintReport:
    """Validate every policy file under `directory` and collect every finding."""
    loaded, issues = load_policy_files(directory)
    errors: list[Finding] = []
    warnings: list[Finding] = []
    skipped: list[Skipped] = []
    if not roster:
        skipped.append(Skipped(level="N3", reason="KNOCK_REGISTRIES not set"))

    if not loaded and not issues:
        errors.append(
            Finding(level="N1", path=".", message=f"no policy file found under {directory}")
        )
        return LintReport(errors=errors, warnings=warnings, skipped=skipped)

    errors.extend(
        Finding(level="N1", path=i.path, loc=list(i.loc) or None, message=i.message) for i in issues
    )

    # repository key -> [(policy name, file)], in claim order
    owners: dict[str, list[tuple[str, str]]] = {}
    for item in loaded:
        found = _lint_policy(item, owners, roster, ca_certs, package_mirrors)
        errors.extend(found.errors)
        warnings.extend(found.warnings)

    errors.extend(_ownership_errors(owners))
    return LintReport(errors=errors, warnings=warnings, skipped=skipped)


def _lint_policy(
    item: LoadedPolicy,
    owners: dict[str, list[tuple[str, str]]],
    roster: dict[str, RegistryConfig],
    ca_certs: dict[str, CACertSource],
    package_mirrors: dict[str, PackageMirror],
) -> _PolicyFindings:
    policy = item.policy
    found = _PolicyFindings(item.path)
    n3: list[str] = []
    refs: list[ResourceRef] = []
    claims: list[AliasClaim] = []
    is_git = isinstance(policy.spec.source, GitSource)

    for resolved in resolve_imports(policy.spec):
        if not is_git:
            refs.extend(_check_steps(resolved, found))
        for dest in resolved.destinations or []:
            key = _repo_key(dest, roster, n3)
            owners.setdefault(key, []).append((policy.metadata.name, item.path))
            claims.extend(_alias_claims(policy, resolved, key))

    for overlap in find_alias_overlaps(claims):
        first, second = overlap.origins
        if overlap.certain:
            found.add(
                "N2",
                f"alias {overlap.alias!r} is written into {overlap.dest_repo!r} "
                f"by imports {first!r} and {second!r}",
            )
        else:
            found.add(
                "N2",
                f"alias templates {overlap.alias!r} written into {overlap.dest_repo!r} "
                f"by imports {first!r} and {second!r} may collide, depending on upstream tags",
                warning=True,
            )

    if roster:
        n3.extend(_check_refs(refs, ca_certs, package_mirrors))
    for message in n3:
        found.add("N3", message)
    return found


def _repo_key(dest: Destination, roster: dict[str, RegistryConfig], n3: list[str]) -> str:
    """The resolved host path with a roster (as reconcile), else the logical name (D4).

    An unresolvable registry is an N3 error, and the logical key keeps N2 running.
    """
    if roster:
        try:
            _name, cfg = resolve_registry(dest.registry, roster)
        except ConfigError as e:
            n3.append(str(e))
        else:
            return f"{cfg.host}/{dest.project}/{dest.repository}"
    return f"{dest.registry or '<default>'}/{dest.project}/{dest.repository}"


def _alias_claims(policy: MirrorPolicy, resolved: ResolvedImport, key: str) -> list[AliasClaim]:
    """The aliases this import writes into `key`, as the planners derive them.

    Registry source: each alias template plus each variant's suffix (RegistryPlanner).
    Git source: the source ref, once (GitPlanner).
    """
    src = policy.spec.source
    if isinstance(src, GitSource):
        return [AliasClaim(key, src.ref, resolved.name)]
    return [
        AliasClaim(key, alias + variant.suffix, resolved.name)
        for variant in expand_variants(resolved)
        for alias in resolved.tags.aliases
    ]


def _check_steps(resolved: ResolvedImport, found: _PolicyFindings) -> list[ResourceRef]:
    """Validate each variant's effective steps as the reconcile plan does (D9).

    A variant's `transform` / `remediate` replaces the import's when it declares one,
    else inherits it (`expand_variants`). Each step goes through the same checks as the
    plan phase: `validate_transform_steps` (vocabulary, role, order), then the params
    model `_resolve_transform` (`params_model`) or `_resolve_remediation`
    (`policy_model()`) uses. Returns the resource references of the valid steps.
    """
    own = {v.name: v for v in resolved.variants or []}
    refs: list[ResourceRef] = []
    for variant in expand_variants(resolved):
        declared = own.get(variant.name)
        for role, steps, preceding in (
            ("transform", variant.transform, []),
            ("remediate", variant.remediate, variant.transform),
        ):
            named = declared is not None and getattr(declared, role) is not None
            where = f"import {resolved.name!r}"
            if named:
                where += f", variant {variant.name!r}"
            for i, step in enumerate(steps):
                try:
                    refs.extend(_check_step(step, role, [*preceding, *steps[:i]]))
                except (PolicyValidationError, ValidationError) as e:
                    found.add("N2", f"{where}: {role} step {step.name!r}: {_describe(e)}")
    return refs


def _check_step(
    step: TransformStep, role: str, preceding: list[TransformStep]
) -> tuple[ResourceRef, ...]:
    validate_transform_steps([step], role=role, preceding=preceding)
    compiler = DEFAULT_REGISTRY.get(step.name)
    model = compiler.params_model if role == "transform" else compiler.policy_model()
    return compiler.resource_refs(model.model_validate(step.params))


def _describe(exc: PolicyValidationError | ValidationError) -> str:
    """One readable line: pydantic errors compacted, other messages as they are."""
    cause = exc if isinstance(exc, ValidationError) else exc.__cause__
    if isinstance(cause, ValidationError):
        return "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" if err["loc"] else err["msg"]
            for err in cause.errors()
        )
    return str(exc)


def _check_refs(
    refs: list[ResourceRef],
    ca_certs: dict[str, CACertSource],
    package_mirrors: dict[str, PackageMirror],
) -> list[str]:
    """Resolve each reference against the configuration and read each CA file (D5)."""
    messages: list[str] = []
    for ref in refs:
        try:
            if ref.kind == "caCert":
                ((_name, src),) = resolve_ca_certs([ref.name], ca_certs)
                if src.path is not None:
                    _read_ca(src.path)
            else:
                resolve_mirror(ref.name, package_mirrors)
        except ConfigError as e:
            messages.append(str(e))
    return messages


def _read_ca(path: str) -> None:
    try:
        Path(path).read_text()
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigError(f"cannot read CA cert file {path!r}: {e}") from e


def _ownership_errors(owners: dict[str, list[tuple[str, str]]]) -> list[Finding]:
    """One error per repository claimed by more than one policy name.

    Same rule as `detect_dest_repo_collisions`, collected instead of raised.
    """
    errors: list[Finding] = []
    for key in sorted(owners):
        claims = owners[key]
        names = sorted({name for name, _path in claims})
        if len(names) < 2:
            continue
        files = list(dict.fromkeys(path for _name, path in claims))
        errors.append(
            Finding(
                level="N2",
                path=files[0],
                message=(
                    f"destination repository {key!r} is claimed by several policies "
                    f"({names}, in {files}); each repository must be owned by exactly one "
                    "policy"
                ),
                related=files[1:],
            )
        )
    return errors
