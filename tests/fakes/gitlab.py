from __future__ import annotations

from houba.errors import GitLabError
from houba.ports.gitlab import GitLabProject, MergeRequest


class FakeGitLabPort:
    def __init__(
        self,
        *,
        projects: list[GitLabProject] | None = None,
        variables: dict[tuple[int, str], str] | None = None,
        next_mr_iid: int = 1,
    ) -> None:
        self._projects = {p.path: p for p in (projects or [])}
        self._variables = variables or {}
        self._next_iid = next_mr_iid
        self.created_mrs: list[tuple[int, str, str, str, str]] = []

    def find_project_by_path(self, path: str) -> GitLabProject:
        try:
            return self._projects[path]
        except KeyError as e:
            raise GitLabError(f"project not found: {path}") from e

    def create_merge_request(
        self,
        *,
        project_id: int,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> MergeRequest:
        self.created_mrs.append((project_id, source_branch, target_branch, title, description))
        mr = MergeRequest(iid=self._next_iid, project_id=project_id)
        self._next_iid += 1
        return mr

    def get_project_variable(self, project_id: int, key: str) -> str:
        try:
            return self._variables[(project_id, key)]
        except KeyError as e:
            raise GitLabError(f"variable not found: project={project_id} key={key}") from e
