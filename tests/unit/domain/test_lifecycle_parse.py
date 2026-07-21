from __future__ import annotations

from datetime import UTC, datetime

from knock.domain.lifecycle import (
    MarkedCandidate,
    MarkIdentity,
    build_pending_deletion_annotations,
    parse_pending_mark,
)


def test_parse_round_trips_the_writer() -> None:
    marked_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    annotations = build_pending_deletion_annotations(
        prefix="io.knock",
        marked_at=marked_at,
        reason="dropped-from-selection",
        policy="redis",
        import_name="v7",
        variant="fips",
    )
    candidate = parse_pending_mark("io.knock", "harbor.example/lib/redis:7.2-fips", annotations)
    assert candidate == MarkedCandidate(
        image_ref="harbor.example/lib/redis:7.2-fips",
        identity=MarkIdentity(policy="redis", import_="v7", variant="fips"),
        marked_at=marked_at,
        reason="dropped-from-selection",
    )


def test_parse_is_lenient_on_missing_keys() -> None:
    candidate = parse_pending_mark("io.knock", "h/r:t", {})
    assert candidate.identity == MarkIdentity(policy="", import_="", variant="")
    assert candidate.marked_at is None
    assert candidate.reason == ""


def test_parse_honours_empty_prefix() -> None:
    # When prefix="", the writer stores lifecycle keys without a prefix namespace
    # but intentionally omits policy/import/variant (no namespace to anchor them).
    # The reader must survive that and return empty-string identity fields.
    annotations = build_pending_deletion_annotations(
        prefix="",
        marked_at=datetime(2026, 6, 1, tzinfo=UTC),
        reason="x",
        policy="p",
        import_name="i",
        variant="v",
    )
    candidate = parse_pending_mark("", "h/r:t", annotations)
    assert candidate.reason == "x"
    assert candidate.identity.policy == ""  # not stored by the writer when prefix=""
