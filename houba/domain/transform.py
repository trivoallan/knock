"""Pure transform domain: vocabulary validation, Dockerfile rendering, content versioning.

No I/O, no config import — the application layer resolves names to data and passes it in.
"""

from __future__ import annotations

from houba.domain.mirror_policy import TransformStep
from houba.errors import PolicyValidationError

ALLOWED_STEPS = ("injectCA", "rewritePackageSources")


def validate_transform_steps(steps: list[TransformStep]) -> None:
    """Reject any step outside the known vocabulary or with malformed params."""
    for step in steps:
        if step.name not in ALLOWED_STEPS:
            raise PolicyValidationError(
                f"unknown transform step {step.name!r}; allowed: {list(ALLOWED_STEPS)}"
            )
        if step.name == "injectCA":
            certs = step.params.get("certs")
            if (
                not isinstance(certs, list)
                or not certs
                or not all(isinstance(c, str) for c in certs)
            ):
                raise PolicyValidationError(
                    "injectCA.certs must be a non-empty list of cert names (strings)"
                )
        elif step.name == "rewritePackageSources":
            mirror = step.params.get("mirror")
            if not isinstance(mirror, str) or not mirror:
                raise PolicyValidationError(
                    "rewritePackageSources.mirror must be a non-empty mirror name (string)"
                )
