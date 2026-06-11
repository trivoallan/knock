"""Registry-driven validation, Dockerfile rendering, and content versioning. Pure."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ValidationError

from houba.domain.mirror_policy import TransformStep
from houba.domain.transforms.registry import DEFAULT_REGISTRY
from houba.errors import PolicyValidationError


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
