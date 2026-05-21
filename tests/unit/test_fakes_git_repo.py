from __future__ import annotations

from pathlib import Path

import pytest

from houba.errors import GitError
from houba.ports.git_repo import GitCommit, GitRef
from tests.fakes.git_repo import FakeGitRepoPort


def test_clone_journaled() -> None:
    fake = FakeGitRepoPort()
    fake.clone("https://gitlab.example.com/g/r.git", Path("/tmp/r"), branch="master")
    assert fake.clones == [("https://gitlab.example.com/g/r.git", Path("/tmp/r"), "master")]


def test_commit_records_message() -> None:
    fake = FakeGitRepoPort()
    fake.add(Path("/tmp/r"), ["a.txt", "b.txt"])
    fake.commit(Path("/tmp/r"), "feat: add files")
    assert fake.commits == [GitCommit(repo=Path("/tmp/r"), message="feat: add files")]


def test_push_and_tag_journaled() -> None:
    fake = FakeGitRepoPort()
    fake.push(Path("/tmp/r"), remote="origin", ref="master")
    fake.tag(Path("/tmp/r"), name="v1.0", message="release")
    assert fake.pushes == [(Path("/tmp/r"), "origin", "master")]
    assert fake.tags == [GitRef(repo=Path("/tmp/r"), name="v1.0", message="release")]


def test_current_revision_returns_seeded() -> None:
    fake = FakeGitRepoPort(revisions={Path("/tmp/r"): "abc123"})
    assert fake.current_revision(Path("/tmp/r")) == "abc123"


def test_current_revision_unknown_raises() -> None:
    fake = FakeGitRepoPort()
    with pytest.raises(GitError):
        fake.current_revision(Path("/tmp/r"))
