"""Parsing et validation du properties.yml d'un produit.

Référence : vars/importProduct.groovy:1292-1347 (setProperties)
et resources/properties.yml.template.
"""

from __future__ import annotations

from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from hub2hub.errors import PropertiesValidationError


class Source(BaseModel):
    registry: str
    repository: str


class Destination(BaseModel):
    harbor: Literal["blue", "orange", "both"]
    project: str
    repository: str


class TagsSpec(BaseModel):
    include_regex: str | None = None
    exclude_regex: list[str] = Field(default_factory=list)
    semver_only: bool = True


class Flags(BaseModel):
    add_apt_repos: bool = False
    add_yum_repos: bool = False
    update_keystore: bool = False
    set_timezone: bool = True


class Eol(BaseModel):
    product: str | None = None


class Archive(BaseModel):
    keep: int = 2
    older_than_days: int = 30


class Properties(BaseModel):
    source: Source
    destination: Destination
    tags: TagsSpec = Field(default_factory=TagsSpec)
    flags: Flags = Field(default_factory=Flags)
    eol: Eol = Field(default_factory=Eol)
    archive: Archive = Field(default_factory=Archive)


def parse_properties(text: str) -> Properties:
    """Parse et valide un properties.yml. Lève PropertiesValidationError en cas d'erreur."""
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise PropertiesValidationError(f"YAML invalide : {e}") from e
    if not isinstance(raw, dict):
        raise PropertiesValidationError("Le document YAML racine doit être un mapping")
    try:
        return Properties.model_validate(raw)
    except ValidationError as e:
        raise PropertiesValidationError(str(e)) from e
