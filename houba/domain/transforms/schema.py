"""Derive the published JSON Schema for the transform-step vocabulary from the registry."""

from __future__ import annotations

from typing import Any

from houba.domain.transforms.registry import BUILTIN_STEPS


def transform_steps_schema() -> dict[str, Any]:
    """A `oneOf` of single-key maps `{stepName: <params schema>}`, one per registered step."""
    return {
        "oneOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {step.name: step.params_model.model_json_schema()},
                "required": [step.name],
            }
            for step in BUILTIN_STEPS
        ]
    }
