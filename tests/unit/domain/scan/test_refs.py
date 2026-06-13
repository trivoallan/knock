from __future__ import annotations

from houba.domain.scan.refs import pin_to_digest

D = "sha256:newdigest"


def test_tag_ref_becomes_digest_pinned() -> None:
    assert pin_to_digest("harbor.corp/lib/redis:7.2.0", D) == f"harbor.corp/lib/redis@{D}"


def test_host_with_port_is_preserved() -> None:
    assert pin_to_digest("localhost:5000/lib/redis:7", D) == f"localhost:5000/lib/redis@{D}"


def test_existing_digest_is_replaced() -> None:
    assert pin_to_digest("harbor.corp/lib/redis@sha256:old", D) == f"harbor.corp/lib/redis@{D}"


def test_ref_without_tag_gets_digest_appended() -> None:
    assert pin_to_digest("harbor.corp/lib/redis", D) == f"harbor.corp/lib/redis@{D}"
