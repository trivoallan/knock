"""Discover and parse MirrorPolicy files under a directory (recursive, §8)."""

from __future__ import annotations

from pathlib import Path

from knock.domain.mirror_policy import MirrorPolicy, parse_mirror_policy
from knock.errors import PolicyValidationError


def load_policy_dir(directory: Path) -> list[MirrorPolicy]:
    policies: list[MirrorPolicy] = []
    for path in sorted(directory.rglob("*")):
        if path.suffix not in (".yml", ".yaml") or not path.is_file():
            continue
        try:
            policies.append(parse_mirror_policy(path.read_text()))
        except PolicyValidationError as e:
            raise PolicyValidationError(f"{path}: {e}") from e
    return policies
