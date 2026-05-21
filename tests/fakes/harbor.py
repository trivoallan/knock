from __future__ import annotations

from dataclasses import dataclass, field

from houba.errors import HarborNotFoundError
from houba.ports.harbor import (
    Artifact,
    ArtifactTag,
    ImmutableTagRule,
    Label,
    Repository,
)


@dataclass
class _Recorded:
    """Journal d'appels pour vérification dans les tests use cases."""

    deleted_repositories: list[tuple[str, str]] = field(default_factory=list)
    deleted_artifacts: list[tuple[str, str, str]] = field(default_factory=list)
    deleted_artifact_tags: list[tuple[str, str, str, str]] = field(default_factory=list)
    created_artifact_tags: list[tuple[str, str, str, str]] = field(default_factory=list)
    added_labels: list[tuple[str, str, str, int]] = field(default_factory=list)
    updated_immutable_rules: list[tuple[str, int, str, str, bool]] = field(default_factory=list)


class FakeHarborPort:
    def __init__(
        self,
        repositories: dict[str, list[Repository]] | None = None,
        artifacts: dict[tuple[str, str], list[Artifact]] | None = None,
        tags_by_artifact: dict[tuple[str, str, str], list[ArtifactTag]] | None = None,
        immutable_rules: dict[str, list[ImmutableTagRule]] | None = None,
        labels: list[Label] | None = None,
    ) -> None:
        self._repositories = repositories or {}
        self._artifacts = artifacts or {}
        self._tags_by_artifact = tags_by_artifact or {}
        self._immutable_rules = immutable_rules or {}
        self._labels: dict[str, Label] = {lab.name: lab for lab in (labels or [])}
        self._next_label_id = max((lab.id for lab in self._labels.values()), default=0) + 1
        self.calls = _Recorded()

    # ---- Reads ----
    def get_repositories(self, project_name: str) -> list[Repository]:
        return list(self._repositories.get(project_name, []))

    def get_artifacts(self, project_name: str, repository_name: str) -> list[Artifact]:
        return list(self._artifacts.get((project_name, repository_name), []))

    def get_artifact(
        self, project_name: str, repository_name: str, reference: str
    ) -> Artifact:
        for art in self._artifacts.get((project_name, repository_name), []):
            if art.digest == reference or reference in art.tags:
                return art
        raise HarborNotFoundError(
            f"{project_name}/{repository_name}@{reference} not found in fake"
        )

    def list_artifact_tags(
        self, project_name: str, repository_name: str, reference: str
    ) -> list[ArtifactTag]:
        return list(self._tags_by_artifact.get((project_name, repository_name, reference), []))

    def list_immutable_tag_rules(self, project_name: str) -> list[ImmutableTagRule]:
        return list(self._immutable_rules.get(project_name, []))

    # ---- Writes ----
    def delete_repository(self, project_name: str, repository_name: str) -> None:
        self.calls.deleted_repositories.append((project_name, repository_name))

    def delete_artifact(
        self, project_name: str, repository_name: str, reference: str
    ) -> None:
        self.calls.deleted_artifacts.append((project_name, repository_name, reference))

    def create_artifact_tag(
        self, project_name: str, repository_name: str, reference: str, tag: str
    ) -> None:
        self.calls.created_artifact_tags.append(
            (project_name, repository_name, reference, tag)
        )

    def delete_artifact_tag(
        self, project_name: str, repository_name: str, reference: str, tag: str
    ) -> None:
        self.calls.deleted_artifact_tags.append(
            (project_name, repository_name, reference, tag)
        )

    def ensure_label(self, name: str) -> Label:
        if name in self._labels:
            return self._labels[name]
        lab = Label(id=self._next_label_id, name=name)
        self._labels[name] = lab
        self._next_label_id += 1
        return lab

    def add_label_to_artifact(
        self,
        project_name: str,
        repository_name: str,
        reference: str,
        label_id: int,
    ) -> None:
        self.calls.added_labels.append(
            (project_name, repository_name, reference, label_id)
        )

    def update_immutable_tag_rule(
        self,
        project_name: str,
        rule_id: int,
        scope_selector: str,
        tag_selector: str,
        disabled: bool,
    ) -> None:
        self.calls.updated_immutable_rules.append(
            (project_name, rule_id, scope_selector, tag_selector, disabled)
        )
