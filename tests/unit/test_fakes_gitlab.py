from __future__ import annotations

import pytest

from houba.errors import GitLabError
from houba.ports.gitlab import GitLabProject, MergeRequest
from tests.fakes.gitlab import FakeGitLabPort


def test_find_project_returns_seeded() -> None:
    proj = GitLabProject(id=42, path="group/repo", default_branch="master")
    fake = FakeGitLabPort(projects=[proj])
    assert fake.find_project_by_path("group/repo") == proj


def test_find_project_missing_raises() -> None:
    fake = FakeGitLabPort()
    with pytest.raises(GitLabError):
        fake.find_project_by_path("group/repo")


def test_create_merge_request_returns_journal() -> None:
    fake = FakeGitLabPort(next_mr_iid=12)
    mr = fake.create_merge_request(
        project_id=42,
        source_branch="feat/x",
        target_branch="master",
        title="feat: x",
        description="body",
    )
    assert mr == MergeRequest(iid=12, project_id=42)
    assert fake.created_mrs == [(42, "feat/x", "master", "feat: x", "body")]


def test_get_project_variable_returns_seeded() -> None:
    fake = FakeGitLabPort(variables={(42, "HOUBA_KEY"): "value"})
    assert fake.get_project_variable(42, "HOUBA_KEY") == "value"


def test_get_project_variable_unknown_raises() -> None:
    fake = FakeGitLabPort()
    with pytest.raises(GitLabError):
        fake.get_project_variable(42, "MISSING")
