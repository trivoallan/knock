from __future__ import annotations

from houba.domain.scan.attestation import (
    SCAN_PREDICATE_TYPE,
    build_scan_statement,
    scan_predicate_json_schema,
)


def _stmt() -> dict:
    return build_scan_statement(
        subject_name="harbor.corp/lib/redis:7.2.0",
        subject_digest="sha256:abc",
        scanner_name="trivy",
        scanner_version="0.50.1",
        fmt="sarif",
        summary={"vuln.critical": "1", "vuln.high": "0"},
        report_digest="sha256:report",
        attested_at="2026-06-13T09:00:00+00:00",
        builder_id="houba://ci",
    )


def test_statement_envelope() -> None:
    s = _stmt()
    assert s["_type"] == "https://in-toto.io/Statement/v1"
    assert s["predicateType"] == SCAN_PREDICATE_TYPE == "https://houba.dev/predicate/scan/v1"
    assert s["subject"] == [{"name": "harbor.corp/lib/redis:7.2.0", "digest": {"sha256": "abc"}}]


def test_predicate_fields() -> None:
    p = _stmt()["predicate"]
    assert p["scanner"] == {"name": "trivy", "version": "0.50.1"}
    assert p["format"] == "sarif"
    assert p["summary"] == {"vuln.critical": "1", "vuln.high": "0"}
    assert p["report_digest"] == "sha256:report"
    assert p["attested_at"] == "2026-06-13T09:00:00+00:00"
    assert p["builder_id"] == "houba://ci"


def test_subject_digest_without_algo_prefix_assumes_sha256() -> None:
    s = build_scan_statement(
        subject_name="x",
        subject_digest="deadbeef",
        scanner_name="trivy",
        scanner_version="",
        fmt="sarif",
        summary={},
        report_digest="",
        attested_at="t",
        builder_id="",
    )
    assert s["subject"][0]["digest"] == {"sha256": "deadbeef"}


def test_json_schema_is_derived() -> None:
    schema = scan_predicate_json_schema()
    assert schema["type"] == "object"
    assert set(schema["properties"]) == {
        "scanner",
        "format",
        "summary",
        "report_digest",
        "attested_at",
        "builder_id",
    }


def test_attested_at_documents_freshness_contract() -> None:
    desc = scan_predicate_json_schema()["properties"]["attested_at"]["description"]
    assert "max-age" in desc
    assert "admission" in desc
    assert "trustworthy" in desc
