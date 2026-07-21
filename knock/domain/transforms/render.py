"""Registry-driven validation, Dockerfile rendering, and content versioning. Pure."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from knock.domain.mirror_policy import TransformStep
from knock.domain.transforms.base import ContextFile, ResolvedStep
from knock.domain.transforms.registry import DEFAULT_REGISTRY
from knock.errors import PolicyValidationError


def validate_transform_steps(steps: Sequence[TransformStep]) -> None:
    """Reject any step outside the registry vocabulary or with malformed params."""
    for step in steps:
        compiler = DEFAULT_REGISTRY.get(step.name)  # PolicyValidationError if unknown
        try:
            compiler.params_model.model_validate(step.params)
        except ValidationError as e:
            raise PolicyValidationError(
                f"invalid params for transform step {step.name!r}: {e}"
            ) from e


@dataclass(frozen=True)
class Rendered:
    dockerfile: str
    context_files: tuple[ContextFile, ...]


def render(resolved_steps: Sequence[ResolvedStep], *, source_ref: str) -> Rendered:
    """Assemble one Dockerfile: FROM <source_ref> + each step's fragment, in policy order."""
    lines = [f"FROM {source_ref}"]
    context_files: list[ContextFile] = []
    for rs in resolved_steps:
        compiler = DEFAULT_REGISTRY.get(rs.step.name)
        params = compiler.params_model.model_validate(rs.step.params)
        frag = compiler.fragment(params, rs.resources)
        lines.extend(frag.instructions)
        context_files.extend(frag.context_files)
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
