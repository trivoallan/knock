from datetime import UTC, datetime

from hub2hub.domain.purge import compute_archives_to_purge


def test_archives_older_than_30_days_purged_keeping_latest_2() -> None:
    now = datetime(2026, 5, 21, tzinfo=UTC)
    archives = [
        "1.36_20240101",  # > 30 j, doit être purgé si pas dans le top 2
        "1.36_20240201",
        "1.36_20240301",  # plus récent
        "1.36_20240215",
        "1.37_20260510",
        "1.37_20260515",
        "1.37_20260520",  # plus récent
    ]

    purged = compute_archives_to_purge(archives, keep=2, older_than_days=30, now=now)

    assert sorted(purged) == sorted(["1.36_20240101", "1.36_20240201"])


def test_keeps_top_n_when_all_recent() -> None:
    now = datetime(2026, 5, 21, tzinfo=UTC)
    archives = ["1.36_20260520", "1.36_20260519"]
    purged = compute_archives_to_purge(archives, keep=2, older_than_days=30, now=now)
    assert purged == []


def test_ignores_non_archive_tags() -> None:
    now = datetime(2026, 5, 21, tzinfo=UTC)
    archives = ["latest", "1.36", "1.36_20240101"]
    purged = compute_archives_to_purge(archives, keep=2, older_than_days=30, now=now)
    assert purged == []  # un seul archive du cycle 1.36, conservé (< keep)


def test_invalid_date_in_suffix_is_ignored() -> None:
    now = datetime(2026, 5, 21, tzinfo=UTC)
    archives = ["1.36_2024xx01", "1.36_20240101", "1.36_20240201", "1.36_20240301"]
    purged = compute_archives_to_purge(archives, keep=2, older_than_days=30, now=now)
    assert "1.36_2024xx01" not in purged  # mal formé, ignoré
    assert "1.36_20240101" in purged
