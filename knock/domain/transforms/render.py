"""Registry-driven validation, Dockerfile rendering, and content versioning. Pure."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from knock.domain.mirror_policy import TransformStep
from knock.domain.transforms.base import ContextFile, ResolvedStep
from knock.domain.transforms.registry import DEFAULT_REGISTRY
from knock.errors import PolicyValidationError, UnsafeSourceUserError

# Which steps each policy list accepts. `transform` is applied to every rebuild; `remediate`
# only to an operation the plan orders remediated (it may re-point sources on a copy-only import).
STEPS_BY_ROLE: dict[str, frozenset[str]] = {
    "transform": frozenset({"injectCA", "rewritePackageSources", "setTimezone"}),
    "remediate": frozenset({"upgradePackages", "rewritePackageSources"}),
}


def validate_transform_steps(
    steps: Sequence[TransformStep],
    *,
    role: str = "transform",
    preceding: Sequence[TransformStep] = (),
) -> None:
    """Reject a step outside the vocabulary or its list, with malformed params, or out of order.

    `preceding` is what runs before this list in the same build: the resolved transform, for a
    remediation list.
    """
    allowed = STEPS_BY_ROLE[role]
    seen: set[str] = {s.name for s in preceding}
    for step in steps:
        compiler = DEFAULT_REGISTRY.get(step.name)  # PolicyValidationError if unknown
        if step.name not in allowed:
            if step.name == "upgradePackages":
                raise PolicyValidationError(
                    "step 'upgradePackages' is a remediation: declare it under `remediate:`, "
                    "applied only to an operation the reconcile plan orders remediated"
                )
            raise PolicyValidationError(
                f"step {step.name!r} is not allowed under `{role}:`; allowed: {sorted(allowed)}"
            )
        if step.name == "upgradePackages" and "epoch" in step.params:
            raise PolicyValidationError(
                "step 'upgradePackages' takes no `epoch`: the epoch now comes from the "
                "remediation order in the reconcile plan (`remediate: {epoch}`)"
            )
        try:
            compiler.policy_model().model_validate(step.params)
        except ValidationError as e:
            raise PolicyValidationError(
                f"invalid params for transform step {step.name!r}: {e}"
            ) from e
        # The one inter-step rule: an upgrade before the sources are rewritten would fetch
        # from the image's public repositories instead of the mirror.
        if step.name == "upgradePackages" and "rewritePackageSources" not in seen:
            raise PolicyValidationError(
                "step 'upgradePackages' requires 'rewritePackageSources' in the resolved "
                "transform or earlier in the same remediation list"
            )
        seen.add(step.name)


@dataclass(frozen=True)
class Rendered:
    dockerfile: str
    context_files: tuple[ContextFile, ...]


# A source that declares one of these runs its transform steps as root already: nothing to
# switch, nothing to restore, and the Dockerfile stays what it was before source users existed.
_ROOT_EQUIVALENT = frozenset({"", "root", "0", "0:0", "root:root"})

# A plain `name` or `uid[:gid]`. `fullmatch`, not `match` with `$`: a trailing newline must
# not slip through, since it would end the USER instruction and start another.
_SAFE_USER = re.compile(r"[A-Za-z0-9._-]{1,64}(:[A-Za-z0-9._-]{1,64})?")


def _restorable_user(source_user: str) -> str | None:
    """The user to restore after the transform steps, or None when the source is root."""
    if source_user in _ROOT_EQUIVALENT:
        return None
    if not _SAFE_USER.fullmatch(source_user):
        shown = repr(source_user[:80])
        raise UnsafeSourceUserError(
            f"source image declares user {shown}, which is not a plain name or uid[:gid]; "
            "refusing to render it into a Dockerfile"
        )
    return source_user


def render(
    resolved_steps: Sequence[ResolvedStep], *, source_ref: str, source_user: str = ""
) -> Rendered:
    """Assemble one Dockerfile: FROM <source_ref> + each step's fragment, in policy order.

    `source_user` is the `User` the source image's config declares. Transform steps write to
    system paths, so a non-root source is switched to root for them and restored afterwards;
    the rebuilt image keeps the identity its source declared.
    """
    restore = _restorable_user(source_user) if resolved_steps else None
    lines = [f"FROM {source_ref}"]
    if restore is not None:
        lines.append("USER root")
    context_files: list[ContextFile] = []
    for rs in resolved_steps:
        compiler = DEFAULT_REGISTRY.get(rs.step.name)
        params = compiler.params_model.model_validate(rs.step.params)
        frag = compiler.fragment(params, rs.resources)
        lines.extend(frag.instructions)
        context_files.extend(frag.context_files)
    if restore is not None:
        lines.append(f"USER {restore}")
    return Rendered(dockerfile="\n".join(lines) + "\n", context_files=tuple(context_files))


def transform_version(resolved_steps: Sequence[ResolvedStep]) -> str:
    """Content hash of the resolved transform: step names/params + resolved resource data.

    Changes when a step/param changes, the step order changes, or a resolved value
    (cert content, mirror URL) changes. Drives transform-aware change detection.
    """
    payload: list[Any] = [
        [
            rs.step.name,
            rs.step.params,
            [
                {
                    "kind": r.kind,
                    "name": r.name,
                    "filename": r.filename,
                    "content": r.content,
                    "apt": r.apt,
                    "apk": r.apk,
                }
                for r in rs.resources
            ],
        ]
        for rs in resolved_steps
    ]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()
