"""Select the concrete tags an import targets (spec §5).

Pure function over a TagSelection and the upstream tag list. Selection order:
(includeRegex matches - excludeRegex), drop non-semver if semverOnly, then union
the explicit `names` that exist upstream (names bypass every filter).
"""

from __future__ import annotations

import re

from knock.domain.mirror_policy import TagSelection
from knock.domain.semver import parse_semver, sort_semver


def select_tags(tags: TagSelection, source_tags: list[str]) -> list[str]:
    include = re.compile(tags.include_regex) if tags.include_regex else None
    excludes = [re.compile(p) for p in tags.exclude_regex]

    selected: set[str] = set()
    for tag in source_tags:
        if include is not None and not include.search(tag):
            continue
        if any(e.search(tag) for e in excludes):
            continue
        if tags.semver_only and parse_semver(tag) is None:
            continue
        selected.add(tag)

    # explicit names bypass every filter, but only if they exist upstream
    source_set = set(source_tags)
    for name in tags.names:
        if name in source_set:
            selected.add(name)

    return sort_semver(list(selected))
