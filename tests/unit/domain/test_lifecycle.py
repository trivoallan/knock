from datetime import UTC, datetime

from houba.domain.lifecycle import (
    PENDING_DELETION_ARTIFACT_TYPE,
    build_pending_deletion_annotations,
)

MARKED_AT = datetime(2026, 6, 12, 8, 0, 0, tzinfo=UTC)


def test_artifact_type_is_the_houba_lifecycle_type() -> None:
    assert PENDING_DELETION_ARTIFACT_TYPE == "application/vnd.houba.lifecycle.pending+json"


def test_full_payload_with_prefix_and_identity() -> None:
    ann = build_pending_deletion_annotations(
        prefix="io.houba",
        marked_at=MARKED_AT,
        reason="dropped-from-selection",
        policy="redis",
        import_name="stable",
        variant="hardened",
    )
    assert ann == {
        "io.houba.lifecycle.state": "pending-deletion",
        "io.houba.lifecycle.marked-at": "2026-06-12T08:00:00+00:00",
        "io.houba.lifecycle.reason": "dropped-from-selection",
        "io.houba.policy": "redis",
        "io.houba.import": "stable",
        "io.houba.variant": "hardened",
    }


def test_variant_omitted_when_empty() -> None:
    ann = build_pending_deletion_annotations(
        prefix="io.houba",
        marked_at=MARKED_AT,
        reason="dropped-from-selection",
        policy="redis",
        import_name="stable",
        variant="",
    )
    assert "io.houba.variant" not in ann
    assert ann["io.houba.import"] == "stable"


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
