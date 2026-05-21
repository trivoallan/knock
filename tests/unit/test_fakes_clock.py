from datetime import UTC, datetime, timedelta

import pytest

from tests.fakes.clock import FakeClock


def test_fake_clock_returns_set_value() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FakeClock(now)
    assert clock.now() == now


def test_fake_clock_advance() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FakeClock(now)
    clock.advance(timedelta(days=2))
    assert clock.now() == datetime(2026, 1, 3, tzinfo=UTC)


def test_fake_clock_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FakeClock(datetime(2026, 1, 1))
