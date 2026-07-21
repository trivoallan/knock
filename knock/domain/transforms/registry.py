"""The built-in transform-step registry. Explicit tuple, no import-time side effects."""

from __future__ import annotations

from typing import Any

from knock.domain.transforms.base import TransformStepCompiler
from knock.domain.transforms.steps import InjectCA, RewritePackageSources, SetTimezone
from knock.errors import PolicyValidationError

BUILTIN_STEPS: tuple[TransformStepCompiler[Any], ...] = (
    InjectCA(),
    RewritePackageSources(),
    SetTimezone(),
)


class Registry:
    def __init__(self, steps: tuple[TransformStepCompiler[Any], ...]) -> None:
        self._by_name: dict[str, TransformStepCompiler[Any]] = {s.name: s for s in steps}

    def get(self, name: str) -> TransformStepCompiler[Any]:
        try:
            return self._by_name[name]
        except KeyError:
            raise PolicyValidationError(
                f"unknown transform step {name!r}; allowed: {sorted(self._by_name)}"
            ) from None

    def names(self) -> frozenset[str]:
        return frozenset(self._by_name)


DEFAULT_REGISTRY = Registry(BUILTIN_STEPS)
