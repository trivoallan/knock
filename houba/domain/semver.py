"""Tri sémantique des tags d'images.

Port direct de sortBySemver / sortBySemverbyField (vars/importProduct.groovy:16-88).
Fonction pure : aucun I/O.
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
    is_non_semver: int  # 1 → pousse en fin de tri
    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease_rank: int = 1  # 0 si pré-release (sorts avant final), 1 si final
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


def sort_semver(values: list[str], *, reverse: bool = False) -> list[str]:
    semver = [v for v in values if _key(v).is_non_semver == 0]
    others = [v for v in values if _key(v).is_non_semver == 1]
    semver.sort(key=_key, reverse=reverse)
    return [*semver, *others]
