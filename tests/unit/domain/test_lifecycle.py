from datetime import UTC, datetime

from knock.domain.lifecycle import (
    PENDING_DELETION_ARTIFACT_TYPE,
    build_pending_deletion_annotations,
)

MARKED_AT = datetime(2026, 6, 12, 8, 0, 0, tzinfo=UTC)


def test_artifact_type_is_the_knock_lifecycle_type() -> None:
    assert PENDING_DELETION_ARTIFACT_TYPE == "application/vnd.knock.lifecycle.pending+json"


def test_full_payload_with_prefix_and_identity() -> None:
    ann = build_pending_deletion_annotations(
        prefix="io.knock",
        marked_at=MARKED_AT,
        reason="dropped-from-selection",
        policy="redis",
        import_name="stable",
        variant="hardened",
    )
    assert ann == {
        "io.knock.lifecycle.state": "pending-deletion",
        "io.knock.lifecycle.marked-at": "2026-06-12T08:00:00+00:00",
        "io.knock.lifecycle.reason": "dropped-from-selection",
        "io.knock.policy": "redis",
        "io.knock.import": "stable",
        "io.knock.variant": "hardened",
    }


def test_variant_omitted_when_empty() -> None:
    ann = build_pending_deletion_annotations(
        prefix="io.knock",
        marked_at=MARKED_AT,
        reason="dropped-from-selection",
        policy="redis",
        import_name="stable",
        variant="",
    )
    assert "io.knock.variant" not in ann
    assert ann["io.knock.import"] == "stable"


def test_empty_prefix_emits_only_bare_lifecycle_keys() -> None:
    ann = build_pending_deletion_annotations(
        prefix="",
        marked_at=MARKED_AT,
        reason="dropped-from-selection",
        policy="redis",
        import_name="stable",
        variant="hardened",
    )
    assert ann == {
        "lifecycle.state": "pending-deletion",
        "lifecycle.marked-at": "2026-06-12T08:00:00+00:00",
        "lifecycle.reason": "dropped-from-selection",
    }
