"""Pure-domain models for the MirrorPolicy declaration (see spec §3).

YAML is camelCase; Python is snake_case. Unknown fields are rejected so typos in
a policy file fail fast (the schema is the public API).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class ArtifactType(StrEnum):
    image = "image"
    helm_chart = "helmChart"
    generic = "generic"


class Source(_CamelModel):
    registry: str
    repository: str


class Destination(_CamelModel):
    # optional iff exactly one registry configured (checked at reconcile time)
    registry: str | None = None
    project: str
    repository: str


class TagSelection(_CamelModel):
    include_regex: str | None = None
    exclude_regex: list[str] = Field(default_factory=list)
    semver_only: bool = True
    names: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


class TransformStep(_CamelModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _from_single_key_map(cls, data: Any) -> Any:
        # Accept the already-split {name, params} form (e.g. when re-validating)...
        if isinstance(data, dict) and set(data.keys()) <= {"name", "params"}:
            return data
        # ...otherwise expect the YAML single-key form {stepName: params}.
        if not isinstance(data, dict) or len(data) != 1:
            raise ValueError("a transform step must be a single-key map {stepName: params}")
        ((name, params),) = data.items()
        return {"name": name, "params": params or {}}
