from __future__ import annotations

from datetime import UTC, datetime

from houba.domain.stamp import build_stamp_annotations

CREATED = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)


def _ann(prefix: str = "io.houba", team: str | None = "platform-data") -> dict[str, str]:
    return build_stamp_annotations(
        prefix=prefix,
        source_registry="docker.io",
        source_repository="library/redis",
        source_tag="7.2.1",
        source_digest="sha256:abc",
        created=CREATED,
        team=team,
        artifact_type="image",
        policy="redis",
        import_name="v7",
        variant="standard",
    )


def test_oci_standard_annotations_always_present() -> None:
    a = _ann()
    assert a["org.opencontainers.image.source"] == "docker.io/library/redis"
    assert a["org.opencontainers.image.revision"] == "7.2.1"
    assert a["org.opencontainers.image.base.name"] == "docker.io/library/redis:7.2.1"
    assert a["org.opencontainers.image.base.digest"] == "sha256:abc"
    assert a["org.opencontainers.image.created"] == "2026-06-11T12:00:00+00:00"


def test_houba_facts_under_prefix() -> None:
    a = _ann(prefix="io.houba")
    assert a["io.houba.team"] == "platform-data"
    assert a["io.houba.artifact.type"] == "image"
    assert a["io.houba.policy"] == "redis"
    assert a["io.houba.import"] == "v7"
    assert a["io.houba.variant"] == "standard"


def test_empty_prefix_drops_houba_facts_keeps_oci() -> None:
    a = _ann(prefix="")
    assert not any(k.startswith("io.houba") for k in a)
    assert "org.opencontainers.image.base.digest" in a


def test_no_team_omits_team_key() -> None:
    a = _ann(team=None)
    assert "io.houba.team" not in a


def test_no_location_fact_stamped() -> None:
    a = _ann()
    assert not any("harbor" in k or "destination" in k or "registry" in k for k in a)
