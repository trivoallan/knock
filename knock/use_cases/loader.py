"""Discover and parse MirrorPolicy files under a directory (recursive, §8)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from knock.domain.mirror_policy import MirrorPolicy, parse_mirror_policy
from knock.errors import PolicyValidationError


@dataclass(frozen=True)
class LoadedPolicy:
    """A successfully parsed policy and its path relative to the scanned directory (POSIX)."""

    path: str
    policy: MirrorPolicy


@dataclass(frozen=True)
class LoadIssue:
    """One problem found in a policy file; `loc` is the path inside the document."""

    path: str
    loc: tuple[str | int, ...]
    message: str


def _scan(directory: Path) -> tuple[list[LoadedPolicy], list[tuple[str, PolicyValidationError]]]:
    loaded: list[LoadedPolicy] = []
    failures: list[tuple[str, PolicyValidationError]] = []
    for path in sorted(directory.rglob("*")):
        if path.suffix not in (".yml", ".yaml") or not path.is_file():
            continue
        rel = path.relative_to(directory).as_posix()
        try:
            loaded.append(LoadedPolicy(rel, parse_mirror_policy(path.read_text())))
        except PolicyValidationError as e:
            failures.append((rel, e))
    return loaded, failures


def load_policy_files(directory: Path) -> tuple[list[LoadedPolicy], list[LoadIssue]]:
    """Parse every policy file under `directory`, collecting every error instead of raising."""
    loaded, failures = _scan(directory)
    issues = [LoadIssue(rel, loc, message) for rel, e in failures for loc, message in e.issues]
    return loaded, issues


def load_policy_dir(directory: Path) -> list[MirrorPolicy]:
    """Parse every policy under `directory`; raise on the first invalid file."""
    loaded, failures = _scan(directory)
    if failures:
        rel, e = failures[0]
        raise PolicyValidationError(f"{directory / rel}: {e}", issues=e.issues) from e
    return [lp.policy for lp in loaded]
