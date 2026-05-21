from __future__ import annotations

from pathlib import Path

import pytest

from houba.adapters.git_cli import GitCliAdapter
from houba.errors import GitError


def _log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    log = tmp_path / "git.log"
    monkeypatch.setenv("FAKE_GIT_LOG", str(log))
    return log


def test_clone_calls_git(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(monkeypatch, tmp_path)
    GitCliAdapter().clone(
        "https://gitlab.example.com/g/r.git", tmp_path / "r", branch="master"
    )
    out = log.read_text()
    assert "clone" in out
    assert "--branch master" in out or "-b master" in out


def test_commit_calls_git_commit(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(monkeypatch, tmp_path)
    GitCliAdapter().commit(tmp_path, "feat: add x")
    assert "commit -m feat: add x" in log.read_text()


def test_push_calls_git_push(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(monkeypatch, tmp_path)
    GitCliAdapter().push(tmp_path, remote="origin", ref="master")
    assert "push origin master" in log.read_text()


def test_tag_calls_git_tag(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(monkeypatch, tmp_path)
    GitCliAdapter().tag(tmp_path, name="v1.0", message="release")
    assert "tag -a v1.0" in log.read_text()


def test_current_revision_returns_rev_parse_output(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_GIT_REVISION", "deadbeef")
    assert GitCliAdapter().current_revision(tmp_path) == "deadbeef"


def test_failure_raises_git_error(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_GIT_SCENARIO", "fail")
    with pytest.raises(GitError):
        GitCliAdapter().push(tmp_path, remote="origin", ref="master")


def test_missing_binary_raises_git_error() -> None:
    with pytest.raises(GitError, match="not found"):
        GitCliAdapter(binary="/nonexistent/git")
