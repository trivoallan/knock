from __future__ import annotations

import json

from houba.domain.attestation import (
    PREDICATE_TYPE,
    SIGNING_CONFIG_MEDIA_TYPE,
    STATEMENT_TYPE,
    build_signing_config,
    build_transform_statement,
    transform_predicate_json_schema,
)


def _statement() -> dict:
    return build_transform_statement(
        subject_name="reg.local/hardened/redis:7.2.5",
        subject_digest="sha256:out123",
        policy="redis-hardened",
        import_name="v7",
        variant="default",
        source="docker.io/library/redis",
        source_digest="sha256:src",
        builder_id="https://houba.example/builders/main",
        created="2026-06-11T00:00:00+00:00",
        transform_version="sha256:tv",
        steps=[("injectCA", {"certs": ["corp"]}), ("rewritePackageSources", {"mirror": "corp"})],
        transformed=True,
    )


def test_statement_envelope_uses_frozen_types() -> None:
    s = _statement()
    assert s["_type"] == STATEMENT_TYPE == "https://in-toto.io/Statement/v1"
    assert s["predicateType"] == PREDICATE_TYPE == "https://houba.dev/predicate/transform/v1"


def test_subject_is_output_digest_in_intoto_shape() -> None:
    [subject] = _statement()["subject"]
    assert subject["name"] == "reg.local/hardened/redis:7.2.5"
    # in-toto subject digest is {algo: hex}, NOT the "sha256:hex" string form
    assert subject["digest"] == {"sha256": "out123"}


def test_predicate_carries_lineage_with_public_import_key() -> None:
    pred = _statement()["predicate"]
    assert pred["policy"] == "redis-hardened"
    assert pred["import"] == "v7"  # public spelling, via alias (mirrors io.houba.import)
    assert pred["variant"] == "default"
    assert pred["source"] == "docker.io/library/redis"
    assert pred["source_digest"] == "sha256:src"
    assert pred["builder_id"] == "https://houba.example/builders/main"
    assert pred["created"] == "2026-06-11T00:00:00+00:00"
    assert pred["transform_version"] == "sha256:tv"
    assert pred["steps"] == [
        {"name": "injectCA", "params": {"certs": ["corp"]}},
        {"name": "rewritePackageSources", "params": {"mirror": "corp"}},
    ]


def test_no_steps_yields_empty_list() -> None:
    s = build_transform_statement(
        subject_name="r:1",
        subject_digest="sha256:out",
        policy="p",
        import_name="i",
        variant="default",
        source="docker.io/library/x",
        source_digest="sha256:s",
        builder_id="",
        created="2026-06-11T00:00:00+00:00",
        transform_version="sha256:tv",
        steps=[],
        transformed=False,
    )
    assert s["predicate"]["steps"] == []


def test_bare_digest_without_algo_prefix_assumed_sha256() -> None:
    s = build_transform_statement(
        subject_name="r:1",
        subject_digest="barehex",
        policy="p",
        import_name="i",
        variant="default",
        source="docker.io/library/x",
        source_digest="sha256:s",
        builder_id="",
        created="2026-06-11T00:00:00+00:00",
        transform_version="sha256:tv",
        steps=[],
        transformed=False,
    )
    assert s["subject"][0]["digest"] == {"sha256": "barehex"}


def test_statement_is_json_serializable() -> None:
    json.dumps(_statement())  # must not raise


def test_rebuild_statement_marks_transformed_true() -> None:
    pred = _statement()["predicate"]  # _statement() passes real steps
    assert pred["transformed"] is True


def test_copy_statement_marks_transformed_false_with_no_steps() -> None:
    s = build_transform_statement(
        subject_name="reg.local/mirror/redis:7.2.5",
        subject_digest="sha256:out",
        policy="redis-mirror",
        import_name="v7",
        variant="default",
        source="docker.io/library/redis",
        source_digest="sha256:src",
        builder_id="https://houba.example/builders/main",
        created="2026-06-15T00:00:00+00:00",
        transform_version="",
        steps=[],
        transformed=False,
    )
    assert s["predicate"]["transformed"] is False
    assert s["predicate"]["steps"] == []


def test_published_schema_is_stable_and_documents_import_alias() -> None:
    schema = transform_predicate_json_schema()
    json.dumps(schema)  # serializable
    assert "import" in schema["properties"]  # the public alias, not "import_"
    assert "import" in schema["required"]
    assert "transformed" in schema["properties"]
    assert "transformed" in schema["required"]


def test_signing_config_empty_is_air_gapped() -> None:
    cfg = build_signing_config(fulcio_url="", rekor_url="", operator="houba")
    assert cfg == {
        "mediaType": SIGNING_CONFIG_MEDIA_TYPE,
        "rekorTlogConfig": {},
        "tsaConfig": {},
    }
    assert SIGNING_CONFIG_MEDIA_TYPE == "application/vnd.dev.sigstore.signingconfig.v0.2+json"


def test_signing_config_rekor_adds_tlog_service() -> None:
    cfg = build_signing_config(fulcio_url="", rekor_url="https://rekor.corp", operator="houba")
    assert cfg["rekorTlogUrls"] == [
        {
            "url": "https://rekor.corp",
            "majorApiVersion": 1,
            "validFor": {"start": "1970-01-01T00:00:00Z"},
            "operator": "houba",
        }
    ]
    assert cfg["rekorTlogConfig"] == {"selector": "ANY"}
    assert "caUrls" not in cfg


def test_signing_config_fulcio_adds_ca_service() -> None:
    cfg = build_signing_config(fulcio_url="https://fulcio.corp", rekor_url="", operator="acme")
    assert cfg["caUrls"] == [
        {
            "url": "https://fulcio.corp",
            "majorApiVersion": 1,
            "validFor": {"start": "1970-01-01T00:00:00Z"},
            "operator": "acme",
        }
    ]
    assert "rekorTlogUrls" not in cfg
    assert cfg["rekorTlogConfig"] == {}


def test_signing_config_both_services_present() -> None:
    cfg = build_signing_config(
        fulcio_url="https://fulcio.corp",
        rekor_url="https://rekor.corp",
        operator="houba",
    )
    assert "caUrls" in cfg
    assert "rekorTlogUrls" in cfg
    assert cfg["rekorTlogConfig"] == {"selector": "ANY"}
