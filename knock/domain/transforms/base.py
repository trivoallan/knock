"""Pure data contracts for the pluggable transform-step vocabulary. No I/O, no config."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel

from knock.domain.mirror_policy import TransformStep


@dataclass(frozen=True)
class ResourceRef:
    """A named resource a step references; resolved to data by the application layer."""

    kind: str  # "caCert" | "packageMirror"
    name: str


@dataclass(frozen=True)
class ResolvedResource:
    """What a per-kind resolver produced for one ResourceRef (tagged by `kind`)."""

    kind: str
    name: str
    filename: str | None = None  # caCert: e.g. "corp.crt"
    content: str | None = None  # caCert: PEM text
    apt: str | None = None  # packageMirror
    apk: str | None = None  # packageMirror


@dataclass(frozen=True)
class ContextFile:
    """A file a step needs written into the build context (path relative to context root)."""

    path: str
    content: str


@dataclass(frozen=True)
class Fragment:
    """A step's contribution to the rebuild: ordered Dockerfile lines + context files."""

    instructions: tuple[str, ...]
    context_files: tuple[ContextFile, ...] = ()


@dataclass(frozen=True)
class ResolvedStep:
    """A transform step paired with its resolved resources (in resource_refs order)."""

    step: TransformStep
    resources: tuple[ResolvedResource, ...] = ()


class TransformStepCompiler[P: BaseModel](ABC):
    """One pluggable transform step. Pure: params + resolved resources -> Fragment."""

    name: ClassVar[str]
    params_model: ClassVar[type[BaseModel]]

    def resource_refs(self, params: P) -> tuple[ResourceRef, ...]:
        return ()

    @abstractmethod
    def fragment(self, params: P, resources: tuple[ResolvedResource, ...]) -> Fragment: ...
