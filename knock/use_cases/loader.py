"""Discover and parse MirrorPolicy files under a directory (recursive, §8)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from knock.domain.mirror_policy import MirrorPolicy, parse_mirror_policy
from knock.errors import Loc, PolicyValidationError


@dataclass(frozen=True)
class LoadedPolicy:
    """A successfully parsed policy and its path relative to the scanned directory (POSIX)."""

    path: str
    policy: MirrorPolicy


@dataclass(frozen=True)
class LoadIssue:
    """One problem found in a policy file; `loc` is the path inside the document."""

    path: str
    loc: Loc
    message: str


def _scan(directory: Path) -> Iterator[LoadedPolicy | tuple[str, Exception]]:
    """Single parse path shared by reconcile and lint (design D1); lazy, one item per file."""
    for path in sorted(directory.rglob("*")):
        if path.suffix not in (".yml", ".yaml") or not path.is_file():
            continue
        rel = path.relative_to(directory).as_posix()
        try:
            yield LoadedPolicy(rel, parse_mirror_policy(path.read_text()))
        except (PolicyValidationError, OSError, UnicodeDecodeError) as e:
            yield rel, e


def load_policy_files(directory: Path) -> tuple[list[LoadedPolicy], list[LoadIssue]]:
    """Parse every policy file under `directory`, collecting every error instead of raising."""
    loaded: list[LoadedPolicy] = []
    issues: list[LoadIssue] = []
    for item in _scan(directory):
        if isinstance(item, LoadedPolicy):
            loaded.append(item)
            continue
        rel, exc = item
        if isinstance(exc, PolicyValidationError):
            issues.extend(LoadIssue(rel, loc, message) for loc, message in exc.issues)
        else:
            issues.append(LoadIssue(rel, (), f"cannot read file: {exc}"))
    return loaded, issues


def load_policy_dir(directory: Path) -> list[MirrorPolicy]:
    """Parse every policy under `directory`; raise on the first invalid file (lazily)."""
    policies: list[MirrorPolicy] = []
    for item in _scan(directory):
        if isinstance(item, LoadedPolicy):
            policies.append(item.policy)
            continue
        rel, exc = item
        if isinstance(exc, PolicyValidationError):
            raise PolicyValidationError(f"{directory / rel}: {exc}", issues=exc.issues) from exc
        raise exc
    return policies
