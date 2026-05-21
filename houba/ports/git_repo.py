"""Port d'accès à un dépôt git local (clone, commit, push, tag)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class GitCommit:
    repo: Path
    message: str


@dataclass(frozen=True)
class GitRef:
    repo: Path
    name: str
    message: str | None = None


class GitRepoPort(Protocol):
    def clone(self, url: str, destination: Path, *, branch: str | None = None) -> None: ...
    def checkout(self, repo: Path, ref: str) -> None: ...
    def add(self, repo: Path, paths: list[str]) -> None: ...
    def commit(self, repo: Path, message: str) -> None: ...
    def push(self, repo: Path, *, remote: str, ref: str) -> None: ...
    def tag(self, repo: Path, *, name: str, message: str | None = None) -> None: ...
    def current_revision(self, repo: Path) -> str: ...
