"""Pure-domain models for the MirrorPolicy declaration (see spec §3).

YAML is camelCase; Python is snake_case. Unknown fields are rejected so typos in
a policy file fail fast (the schema is the public API).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
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
