import pytest

from houba.errors import HarborNotFoundError
from houba.ports.harbor import (
    Artifact,
    ArtifactTag,
    ImmutableTagRule,
    Label,
    Repository,
)
from tests.fakes.harbor import FakeHarborPort


def test_get_repositories_returns_seeded() -> None:
    repos = [Repository(name="rancher/k3s", project_id=1)]
    harbor = FakeHarborPort(repositories={"04228.proxy.docker.io": repos})

    assert harbor.get_repositories("04228.proxy.docker.io") == repos


def test_get_artifacts_returns_seeded() -> None:
    arts = [Artifact(digest="sha256:abc", tags=["v1.0.0"], push_time="2026-01-01T00:00:00Z")]
    harbor = FakeHarborPort(artifacts={("04228.proxy.docker.io", "rancher/k3s"): arts})

    assert harbor.get_artifacts("04228.proxy.docker.io", "rancher/k3s") == arts


def test_get_artifacts_unknown_returns_empty() -> None:
    harbor = FakeHarborPort()
    assert harbor.get_artifacts("p", "r") == []


def test_get_artifact_by_digest() -> None:
    art = Artifact(digest="sha256:abc", tags=["1.36"])
    fake = FakeHarborPort(artifacts={("lib", "busybox"): [art]})
    assert fake.get_artifact("lib", "busybox", "sha256:abc") == art


def test_get_artifact_by_tag() -> None:
    art = Artifact(digest="sha256:abc", tags=["1.36", "latest"])
    fake = FakeHarborPort(artifacts={("lib", "busybox"): [art]})
    assert fake.get_artifact("lib", "busybox", "latest") == art


def test_get_artifact_missing_raises() -> None:
    fake = FakeHarborPort()
    with pytest.raises(HarborNotFoundError):
        fake.get_artifact("lib", "busybox", "missing")


def test_list_artifact_tags() -> None:
    tags = [ArtifactTag(name="1.36"), ArtifactTag(name="latest", immutable=True)]
    fake = FakeHarborPort(tags_by_artifact={("lib", "busybox", "sha256:abc"): tags})
    assert fake.list_artifact_tags("lib", "busybox", "sha256:abc") == tags


def test_list_immutable_tag_rules() -> None:
    rule = ImmutableTagRule(id=1, scope_selector="**", tag_selector="*", disabled=False)
    fake = FakeHarborPort(immutable_rules={"lib": [rule]})
    assert fake.list_immutable_tag_rules("lib") == [rule]


def test_delete_repository_is_journaled() -> None:
    fake = FakeHarborPort()
    fake.delete_repository("lib", "busybox")
    assert fake.calls.deleted_repositories == [("lib", "busybox")]


def test_delete_artifact_is_journaled() -> None:
    fake = FakeHarborPort()
    fake.delete_artifact("lib", "busybox", "sha256:abc")
    assert fake.calls.deleted_artifacts == [("lib", "busybox", "sha256:abc")]


def test_create_artifact_tag_is_journaled() -> None:
    fake = FakeHarborPort()
    fake.create_artifact_tag("lib", "busybox", "sha256:abc", "1.36")
    assert fake.calls.created_artifact_tags == [("lib", "busybox", "sha256:abc", "1.36")]


def test_delete_artifact_tag_is_journaled() -> None:
    fake = FakeHarborPort()
    fake.delete_artifact_tag("lib", "busybox", "sha256:abc", "old")
    assert fake.calls.deleted_artifact_tags == [("lib", "busybox", "sha256:abc", "old")]


def test_ensure_label_returns_existing() -> None:
    pre = Label(id=7, name="io.houba.source.tag=1.36")
    fake = FakeHarborPort(labels=[pre])
    assert fake.ensure_label("io.houba.source.tag=1.36") is pre


def test_ensure_label_creates_when_missing() -> None:
    fake = FakeHarborPort()
    lab = fake.ensure_label("io.houba.source.tag=1.36")
    assert lab.id >= 1
    assert lab.name == "io.houba.source.tag=1.36"
    # Second call with same name returns same label
    assert fake.ensure_label("io.houba.source.tag=1.36").id == lab.id
    # Second call with a *different* name gets a different id
    other = fake.ensure_label("io.houba.source.tag=2.0")
    assert other.id != lab.id


def test_add_label_to_artifact_is_journaled() -> None:
    fake = FakeHarborPort()
    fake.add_label_to_artifact("lib", "busybox", "sha256:abc", 7)
    assert fake.calls.added_labels == [("lib", "busybox", "sha256:abc", 7)]


def test_update_immutable_tag_rule_is_journaled() -> None:
    fake = FakeHarborPort()
    fake.update_immutable_tag_rule("lib", 1, "**", "v*", True)
    assert fake.calls.updated_immutable_rules == [("lib", 1, "**", "v*", True)]
