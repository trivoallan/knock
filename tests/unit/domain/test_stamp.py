from __future__ import annotations

from datetime import UTC, datetime

from houba.domain.stamp import build_stamp_annotations

CREATED = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)


def _ann(
    prefix: str = "io.houba",
    owners: list[str] | None = None,
    source_revision: str | None = None,
) -> dict[str, str]:
    return build_stamp_annotations(
        prefix=prefix,
        source_registry="docker.io",
        source_repository="library/redis",
        source_tag="7.2.1",
        source_digest="sha256:abc",
        source_revision=source_revision,
        created=CREATED,
        owners=owners,
        artifact_type="image",
        policy="redis",
        import_name="v7",
        variant="standard",
    )


def test_oci_standard_annotations_always_present() -> None:
    a = _ann()
    assert a["org.opencontainers.image.source"] == "docker.io/library/redis"
    assert a["org.opencontainers.image.base.name"] == "docker.io/library/redis:7.2.1"
    assert a["org.opencontainers.image.base.digest"] == "sha256:abc"
    assert a["org.opencontainers.image.created"] == "2026-06-11T12:00:00+00:00"


def test_revision_omitted_when_source_declares_none() -> None:
    a = _ann(source_revision=None)
    assert "org.opencontainers.image.revision" not in a


def test_revision_is_the_propagated_source_revision() -> None:
    a = _ann(source_revision="9fceb02")  # an upstream SCM commit, NOT the source digest
    assert a["org.opencontainers.image.revision"] == "9fceb02"
    assert a["org.opencontainers.image.revision"] != a["org.opencontainers.image.base.digest"]


def test_houba_facts_under_prefix() -> None:
    a = _ann(prefix="io.houba", owners=["group:default/payments", "group:default/data"])
    assert a["io.houba.owners"] == "group:default/payments,group:default/data"
    assert a["io.houba.artifact.type"] == "image"
    assert a["io.houba.policy"] == "redis"
    assert a["io.houba.import"] == "v7"
    assert a["io.houba.variant"] == "standard"
    assert "io.houba.owner.team" not in a


def test_no_owners_omits_owners_key() -> None:
    a = _ann(owners=None)
    assert "io.houba.owners" not in a


def test_empty_owners_omits_owners_key() -> None:
    a = _ann(owners=[])
    assert "io.houba.owners" not in a


def test_empty_prefix_drops_houba_facts_keeps_oci() -> None:
    a = _ann(prefix="")
    assert not any(k.startswith("io.houba") for k in a)
    assert "org.opencontainers.image.base.digest" in a


def test_no_location_fact_stamped() -> None:
    a = _ann()
    assert not any("harbor" in k or "destination" in k or "registry" in k for k in a)


# ---------------------------------------------------------------------------
# transform lineage keys
# ---------------------------------------------------------------------------


def _base_kwargs() -> dict:
    return dict(
        prefix="io.houba",
        source_registry="docker.io",
        source_repository="library/redis",
        source_tag="7.2.0",
        source_digest="sha256:src",
        source_revision=None,
        created=datetime(2026, 6, 11, tzinfo=UTC),
        owners=None,
        artifact_type="image",
        policy="redis-hardened",
        import_name="v7",
        variant="default",
    )


def test_stamp_without_transform_has_no_transform_keys() -> None:
    ann = build_stamp_annotations(**_base_kwargs())
    assert not any(".transform." in k for k in ann)


def test_stamp_with_transform_emits_steps_and_version() -> None:
    ann = build_stamp_annotations(
        **_base_kwargs(),
        transform_steps=["injectCA", "rewritePackageSources"],
        transform_version_value="sha256:tv",
    )
    assert ann["io.houba.transform.steps"] == "injectCA,rewritePackageSources"
    assert ann["io.houba.transform.version"] == "sha256:tv"
