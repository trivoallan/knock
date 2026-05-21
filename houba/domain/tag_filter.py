"""Calcul des tags à importer / mettre à jour / supprimer.

Port de retrieveTagsToImport (vars/importProduct.groovy:1607-1804).
Fonction pure : aucun I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from houba.domain.properties import Properties
from houba.domain.semver import sort_semver
from houba.errors import PropertiesValidationError

DIGEST_CHANGE_GRACE = timedelta(days=7)
_SEMVER_RE = re.compile(r"^v?\d+(\.\d+){0,2}(-[0-9A-Za-z.-]+)?$")


@dataclass(frozen=True)
class HarborTagState:
    digest: str
    push_time: datetime


@dataclass(frozen=True)
class TagsDecision:
    to_import: list[str] = field(default_factory=list)
    to_update: list[str] = field(default_factory=list)
    to_delete: list[str] = field(default_factory=list)


def _compile(pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as e:
        raise PropertiesValidationError(f"regex invalide '{pattern}': {e}") from e


def compute_tags_to_import(
    *,
    src_tags: list[str],
    src_digests: dict[str, tuple[str, datetime]],
    properties: Properties,
    harbor_state: dict[str, HarborTagState],
    now: datetime,
) -> TagsDecision:
    include = _compile(properties.tags.include_regex) if properties.tags.include_regex else None
    excludes = [_compile(p) for p in properties.tags.exclude_regex]

    candidates: list[str] = []
    for tag in src_tags:
        if properties.tags.semver_only and not _SEMVER_RE.match(tag):
            continue
        if include and not include.search(tag):
            continue
        if any(ex.search(tag) for ex in excludes):
            continue
        candidates.append(tag)

    candidates = sort_semver(candidates)

    to_import: list[str] = []
    to_update: list[str] = []
    for tag in candidates:
        src_digest, src_push_time = src_digests[tag]
        harbor = harbor_state.get(tag)
        if harbor is None:
            to_import.append(tag)
            continue
        if harbor.digest == src_digest:
            continue
        if now - src_push_time < DIGEST_CHANGE_GRACE:
            continue
        to_update.append(tag)

    src_set = set(src_tags)
    to_delete = [tag for tag in harbor_state if tag not in src_set]

    return TagsDecision(to_import=to_import, to_update=to_update, to_delete=to_delete)
