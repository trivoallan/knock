from houba.ports.reporter import Counts, OperationEvent


def test_counts_has_marked_defaulting_to_zero() -> None:
    assert Counts().marked == 0
    assert Counts(marked=3).marked == 3


def test_operation_event_accepts_marked_kind() -> None:
    ev = OperationEvent(
        policy="redis",
        dest_repo="harbor.corp/lib/redis",
        variant="",
        kind="marked",
        out_tag="6.0.0",
        src_tag=None,
        digest=None,
        applied=True,
    )
    assert ev.kind == "marked"
