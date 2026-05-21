"""Port d'accès à l'API REST GitLab (minimal Phase B)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GitLabProject:
    id: int
    path: str
    default_branch: str = "master"


@dataclass(frozen=True)
class MergeRequest:
    iid: int
    project_id: int


class GitLabPort(Protocol):
    def find_project_by_path(self, path: str) -> GitLabProject: ...
    def create_merge_request(
        self,
        *,
        project_id: int,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> MergeRequest: ...
    def get_project_variable(self, project_id: int, key: str) -> str: ...
