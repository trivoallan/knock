from houba.domain.deletion_mode import DeletionMode, resolve_deletion_mode


def test_policy_wins_over_destination_and_global() -> None:
    assert (
        resolve_deletion_mode(DeletionMode.mark, DeletionMode.purge, DeletionMode.purge)
        == DeletionMode.mark
    )


def test_destination_used_when_policy_unset() -> None:
    assert resolve_deletion_mode(None, DeletionMode.mark, DeletionMode.purge) == DeletionMode.mark


def test_global_used_when_policy_and_destination_unset() -> None:
    assert resolve_deletion_mode(None, None, DeletionMode.purge) == DeletionMode.purge


def test_enum_values_are_the_wire_strings() -> None:
    assert DeletionMode.purge.value == "purge"
    assert DeletionMode.mark.value == "mark"
