from __future__ import annotations

from typing import get_type_hints

from houba.ports.harbor import (
    ArtifactTag,
    HarborPort,
    ImmutableTagRule,
    Label,
)


def test_label_dataclass_has_id_and_name() -> None:
    lab = Label(id=42, name="fr.sncf.h2h.source.tag=1.36")
    assert lab.id == 42
    assert lab.name == "fr.sncf.h2h.source.tag=1.36"


def test_artifact_tag_dataclass() -> None:
    t = ArtifactTag(name="1.36", immutable=False)
    assert t.name == "1.36"
    assert t.immutable is False


def test_immutable_tag_rule_dataclass() -> None:
    r = ImmutableTagRule(
        id=1,
        scope_selector="**",
        tag_selector="*",
        disabled=False,
    )
    assert r.id == 1
    assert r.disabled is False


def test_harbor_port_has_no_class_level_annotations() -> None:
    hints = get_type_hints(HarborPort)
    # Protocol has no annotated class-level attributes; methods are tested via FakeHarborPort.
    assert hints == {}


def test_harbor_port_protocol_runtime_check() -> None:
    """FakeHarborPort doit satisfaire HarborPort (protocole structurel)."""
    from tests.fakes.harbor import FakeHarborPort

    fake: HarborPort = FakeHarborPort()
    # Les méthodes read et write doivent toutes être présentes
    assert callable(fake.get_repositories)
    assert callable(fake.get_artifacts)
    assert callable(fake.get_artifact)
    assert callable(fake.list_artifact_tags)
    assert callable(fake.delete_repository)
    assert callable(fake.delete_artifact)
    assert callable(fake.create_artifact_tag)
    assert callable(fake.delete_artifact_tag)
    assert callable(fake.ensure_label)
    assert callable(fake.add_label_to_artifact)
    assert callable(fake.list_immutable_tag_rules)
    assert callable(fake.update_immutable_tag_rule)
