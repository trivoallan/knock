"""Port d'accès à Harbor v2 (lectures uniquement en Phase A).

Voir spec §4. Les méthodes d'écriture (copy_artifact, delete_artifact_tag,
add_artifact_tag, update_immutabletagrule) seront ajoutées en Phase B.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Repository:
    name: str
    project_id: int
    artifact_count: int = 0


@dataclass(frozen=True)
class Artifact:
    digest: str
    tags: list[str] = field(default_factory=list)
    push_time: str = ""
    labels: list[str] = field(default_factory=list)


class HarborPort(Protocol):
    def get_repositories(self, project_name: str) -> list[Repository]: ...
    def get_artifacts(self, project_name: str, repository_name: str) -> list[Artifact]: ...
