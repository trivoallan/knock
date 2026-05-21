from __future__ import annotations

from hub2hub.ports.harbor import Artifact, Repository


class FakeHarborPort:
    def __init__(
        self,
        repositories: dict[str, list[Repository]] | None = None,
        artifacts: dict[tuple[str, str], list[Artifact]] | None = None,
    ) -> None:
        self._repositories = repositories or {}
        self._artifacts = artifacts or {}

    def get_repositories(self, project_name: str) -> list[Repository]:
        return list(self._repositories.get(project_name, []))

    def get_artifacts(self, project_name: str, repository_name: str) -> list[Artifact]:
        return list(self._artifacts.get((project_name, repository_name), []))
