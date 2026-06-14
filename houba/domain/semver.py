"""Semantic sorting of image tags.

Direct port of sortBySemver / sortBySemverbyField (vars/importProduct.groovy:16-88).
Pure function: no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SEMVER_RE = re.compile(
    r"""^v?
        (?P<major>\d+)
        (?:\.(?P<minor>\d+))?
        (?:\.(?P<patch>\d+))?
        (?:-(?P<prerelease>[0-9A-Za-z.-]+))?
        $""",
    re.VERBOSE,
)


@dataclass(frozen=True, order=True)
class _Key:
    is_non_semver: int  # 1 → pushed to the end of the sort
    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease_rank: int = 1  # 0 for pre-release (sorts before final), 1 for final
    prerelease: str = ""


def _key(value: str) -> _Key:
    m = _SEMVER_RE.match(value.strip())
    if not m:
        return _Key(is_non_semver=1)
    major = int(m.group("major"))
    minor = int(m.group("minor") or 0)
    patch = int(m.group("patch") or 0)
    pre = m.group("prerelease") or ""
    return _Key(
        is_non_semver=0,
        major=major,
        minor=minor,
        patch=patch,
        prerelease_rank=0 if pre else 1,
        prerelease=pre,
    )


@dataclass(frozen=True)
class SemverParts:
    major: int
    minor: int
    patch: int


def parse_semver(value: str) -> SemverParts | None:
    """Parse a tag's semver components, or None if it is not semver.

    Accepts an optional leading `v` and partial versions (`2`, `3.4`); a
    prerelease suffix is allowed but ignored for the components.
    """
    m = _SEMVER_RE.match(value.strip())
    if not m:
        return None
    return SemverParts(
        major=int(m.group("major")),
        minor=int(m.group("minor") or 0),
        patch=int(m.group("patch") or 0),
    )


def sort_semver(values: list[str], *, reverse: bool = False) -> list[str]:
    semver = [v for v in values if _key(v).is_non_semver == 0]
    others = [v for v in values if _key(v).is_non_semver == 1]
    semver.sort(key=_key, reverse=reverse)
    return [*semver, *others]
