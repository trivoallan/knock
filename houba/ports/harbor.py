"""Port d'accès à Harbor v2 (lectures + écritures).

Voir spec §4, §7.
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


@dataclass(frozen=True)
class ArtifactTag:
    name: str
    immutable: bool = False


@dataclass(frozen=True)
class Label:
    id: int
    name: str


@dataclass(frozen=True)
class ImmutableTagRule:
    id: int
    scope_selector: str
    tag_selector: str
    disabled: bool = False


class HarborPort(Protocol):
    # ---- Reads ----
    def get_repositories(self, project_name: str) -> list[Repository]: ...
    def get_artifacts(self, project_name: str, repository_name: str) -> list[Artifact]: ...
    def get_artifact(self, project_name: str, repository_name: str, reference: str) -> Artifact: ...
    def list_artifact_tags(
        self, project_name: str, repository_name: str, reference: str
    ) -> list[ArtifactTag]: ...
    def list_immutable_tag_rules(self, project_name: str) -> list[ImmutableTagRule]: ...

    # ---- Writes ----
    def delete_repository(self, project_name: str, repository_name: str) -> None: ...
    def delete_artifact(self, project_name: str, repository_name: str, reference: str) -> None: ...
    def create_artifact_tag(
        self, project_name: str, repository_name: str, reference: str, tag: str
    ) -> None: ...
    def delete_artifact_tag(
        self, project_name: str, repository_name: str, reference: str, tag: str
    ) -> None: ...
    def ensure_label(self, name: str) -> Label: ...
    def add_label_to_artifact(
        self,
        project_name: str,
        repository_name: str,
        reference: str,
        label_id: int,
    ) -> None: ...
    def update_immutable_tag_rule(
        self,
        project_name: str,
        rule_id: int,
        scope_selector: str,
        tag_selector: str,
        disabled: bool,
    ) -> None: ...
