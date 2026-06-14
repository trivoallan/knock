"""Pure-domain models for the MirrorPolicy declaration (see spec §3).

YAML is camelCase; Python is snake_case. Unknown fields are rejected so typos in
a policy file fail fast (the schema is the public API).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic.alias_generators import to_camel

from houba.domain.deletion_mode import DeletionMode
from houba.errors import PolicyValidationError


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
    """One transform step.

    YAML encodes it as a single-key map ``{stepName: params}``; parsed to ``{name, params}``.
    """

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


class Archive(_CamelModel):
    keep: int | None = None
    older_than_days: int | None = None


class Variant(_CamelModel):
    name: str
    suffix: str = ""
    transform: list[TransformStep] | None = None  # None ⇒ inherit resolved transform


class Defaults(_CamelModel):
    destinations: list[Destination] | None = None
    transform: list[TransformStep] | None = None
    archive: Archive | None = None
    tags: TagSelection | None = None
    platforms: list[str] | None = None


class ImportProfile(_CamelModel):
    name: str
    tags: TagSelection
    destinations: list[Destination] | None = None
    transform: list[TransformStep] | None = None
    archive: Archive | None = None
    platforms: list[str] | None = None
    variants: list[Variant] | None = None


class Spec(_CamelModel):
    artifact_type: ArtifactType
    source: Source
    deletion_mode: DeletionMode | None = None  # None ⇒ defer to destination/global cascade
    defaults: Defaults | None = None
    imports: list[ImportProfile] = Field(min_length=1)

    @model_validator(mode="after")
    def _generic_has_no_transform(self) -> Self:
        if self.artifact_type is not ArtifactType.generic:
            return self
        if self.defaults is not None and self.defaults.transform:
            raise PolicyValidationError("artifactType 'generic' must not declare transform steps")
        for imp in self.imports:
            if imp.transform:
                raise PolicyValidationError(
                    f"artifactType 'generic' must not declare transform steps (import '{imp.name}')"
                )
        return self


class Metadata(_CamelModel):
    name: str
    labels: dict[str, str] = Field(default_factory=dict)


class MirrorPolicy(_CamelModel):
    api_version: Literal["houba.io/v1alpha1"]
    kind: Literal["MirrorPolicy"]
    metadata: Metadata
    spec: Spec


def parse_mirror_policy(text: str) -> MirrorPolicy:
    """Parse and validate a MirrorPolicy YAML document.

    Raises PolicyValidationError on malformed YAML, a non-mapping root, an unknown
    field, a wrong kind/apiVersion, or any schema/semantic violation.
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise PolicyValidationError(f"invalid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise PolicyValidationError("the root YAML document must be a mapping")
    try:
        return MirrorPolicy.model_validate(raw)
    except ValidationError as e:
        raise PolicyValidationError(str(e)) from e


def mirror_policy_json_schema() -> dict[str, Any]:
    """The JSON Schema for a MirrorPolicy, keyed by the public (camelCase) field names.

    Published for editor/CI validation of policy files (see CLAUDE.md: JSON Schema
    systematically). Derived from the Pydantic models — never hand-written.

    Note: transform steps are authored in YAML as a single-key map ``{stepName: params}``.
    The published ``TransformStep`` definition is a discriminated ``oneOf`` over the
    registered steps (derived from each step's params model — see
    ``houba.domain.transforms.schema``), so editors/CI validate the authoring YAML form
    and each step's params.
    """
    schema = MirrorPolicy.model_json_schema(by_alias=True)
    # Tighten the open {name, params} TransformStep into a discriminated union derived
    # from the registry, so editors/CI validate per-step params (the authoring YAML form).
    from houba.domain.transforms.schema import transform_steps_schema

    defs = schema.get("$defs", {})
    if "TransformStep" in defs:
        defs["TransformStep"] = transform_steps_schema()
    return schema
