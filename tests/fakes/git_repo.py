from __future__ import annotations

from pathlib import Path

from houba.errors import GitError
from houba.ports.git_repo import GitCommit, GitRef


class FakeGitRepoPort:
    def __init__(self, *, revisions: dict[Path, str] | None = None) -> None:
        self._revisions = revisions or {}
        self.clones: list[tuple[str, Path, str | None]] = []
        self.checkouts: list[tuple[Path, str]] = []
        self.adds: list[tuple[Path, list[str]]] = []
        self.commits: list[GitCommit] = []
        self.pushes: list[tuple[Path, str, str]] = []
        self.tags: list[GitRef] = []

    def clone(self, url: str, destination: Path, *, branch: str | None = None) -> None:
        self.clones.append((url, destination, branch))

    def checkout(self, repo: Path, ref: str) -> None:
        self.checkouts.append((repo, ref))

    def add(self, repo: Path, paths: list[str]) -> None:
        self.adds.append((repo, list(paths)))

    def commit(self, repo: Path, message: str) -> None:
        self.commits.append(GitCommit(repo=repo, message=message))

    def push(self, repo: Path, *, remote: str, ref: str) -> None:
        self.pushes.append((repo, remote, ref))

    def tag(self, repo: Path, *, name: str, message: str | None = None) -> None:
        self.tags.append(GitRef(repo=repo, name=name, message=message))

    def current_revision(self, repo: Path) -> str:
        try:
            return self._revisions[repo]
        except KeyError as e:
            raise GitError(f"no revision known for {repo}") from e
