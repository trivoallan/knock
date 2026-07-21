from __future__ import annotations

from knock.domain.scan.refs import pin_to_digest, registry_host

D = "sha256:newdigest"


def test_tag_ref_becomes_digest_pinned() -> None:
    assert pin_to_digest("harbor.corp/lib/redis:7.2.0", D) == f"harbor.corp/lib/redis@{D}"


def test_host_with_port_is_preserved() -> None:
    assert pin_to_digest("localhost:5000/lib/redis:7", D) == f"localhost:5000/lib/redis@{D}"


def test_existing_digest_is_replaced() -> None:
    assert pin_to_digest("harbor.corp/lib/redis@sha256:old", D) == f"harbor.corp/lib/redis@{D}"


def test_ref_without_tag_gets_digest_appended() -> None:
    assert pin_to_digest("harbor.corp/lib/redis", D) == f"harbor.corp/lib/redis@{D}"


def test_registry_host_with_dot() -> None:
    assert registry_host("harbor.corp/lib/redis:7.2.0") == "harbor.corp"


def test_registry_host_with_port() -> None:
    assert registry_host("localhost:5000/lib/redis:7") == "localhost:5000"


def test_registry_host_localhost_no_port() -> None:
    assert registry_host("localhost/lib/redis:7") == "localhost"


def test_registry_host_bare_name_is_none() -> None:
    assert registry_host("redis:7.2.0") is None


def test_registry_host_single_org_segment_is_none() -> None:
    assert registry_host("library/redis:7.2.0") is None


def test_registry_host_digest_pinned_ref() -> None:
    assert registry_host("harbor.corp/lib/redis@sha256:abc") == "harbor.corp"
