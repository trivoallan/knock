from __future__ import annotations

from datetime import UTC, datetime, timedelta

from houba.domain.purge import PurgeDecision, decide_purge, usage_window_start


def test_window_start_subtracts_idle() -> None:
    now = datetime(2026, 6, 13, tzinfo=UTC)
    assert usage_window_start(now, timedelta(days=15)) == datetime(2026, 5, 29, tzinfo=UTC)


def test_seen_in_window_protects() -> None:
    seen = datetime(2026, 6, 10, tzinfo=UTC)
    assert decide_purge(seen, observed=True) is PurgeDecision.protect


def test_not_seen_purges() -> None:
    assert decide_purge(None, observed=True) is PurgeDecision.purge


def test_oracle_unobserved_is_uncertain() -> None:
    assert decide_purge(None, observed=False) is PurgeDecision.uncertain
