from __future__ import annotations

import pytest
import respx
import httpx

from houba.adapters.gitlab_http import GitLabHttpAdapter
from houba.errors import GitLabError
from houba.ports.gitlab import GitLabProject


@pytest.fixture()
def adapter() -> GitLabHttpAdapter:
    return GitLabHttpAdapter(base_url="https://gitlab.example.com", token="glpat-xxx")


def test_find_project_by_path_returns_project(adapter: GitLabHttpAdapter) -> None:
    with respx.mock(base_url="https://gitlab.example.com") as router:
        router.get(
            "/api/v4/projects/group%2Frepo"
        ).respond(200, json={"id": 42, "path_with_namespace": "group/repo", "default_branch": "main"})
        proj = adapter.find_project_by_path("group/repo")
        assert proj == GitLabProject(id=42, path="group/repo", default_branch="main")


def test_find_project_404_raises_gitlab_error(adapter: GitLabHttpAdapter) -> None:
    with respx.mock(base_url="https://gitlab.example.com") as router:
        router.get("/api/v4/projects/group%2Fmissing").respond(404)
        with pytest.raises(GitLabError):
            adapter.find_project_by_path("group/missing")


def test_create_merge_request(adapter: GitLabHttpAdapter) -> None:
    with respx.mock(base_url="https://gitlab.example.com") as router:
        route = router.post(
            "/api/v4/projects/42/merge_requests",
            json={
                "source_branch": "feat/x",
                "target_branch": "master",
                "title": "feat: x",
                "description": "body",
            },
        ).respond(201, json={"iid": 7, "project_id": 42})
        mr = adapter.create_merge_request(
            project_id=42,
            source_branch="feat/x",
            target_branch="master",
            title="feat: x",
            description="body",
        )
        assert route.called
        assert mr.iid == 7


def test_get_project_variable(adapter: GitLabHttpAdapter) -> None:
    with respx.mock(base_url="https://gitlab.example.com") as router:
        router.get("/api/v4/projects/42/variables/HOUBA_KEY").respond(
            200, json={"key": "HOUBA_KEY", "value": "v", "variable_type": "env_var"}
        )
        assert adapter.get_project_variable(42, "HOUBA_KEY") == "v"


def test_get_project_variable_404_raises_gitlab_error(adapter: GitLabHttpAdapter) -> None:
    with respx.mock(base_url="https://gitlab.example.com") as router:
        router.get("/api/v4/projects/42/variables/MISSING").respond(404)
        with pytest.raises(GitLabError):
            adapter.get_project_variable(42, "MISSING")


def test_transient_5xx_retried(adapter: GitLabHttpAdapter) -> None:
    with respx.mock(base_url="https://gitlab.example.com") as router:
        responses = [
            httpx.Response(503),
            httpx.Response(200, json={"id": 1, "path_with_namespace": "g/r", "default_branch": "master"}),
        ]
        route = router.get("/api/v4/projects/g%2Fr").mock(side_effect=responses)
        adapter.find_project_by_path("g/r")
        assert route.call_count == 2
