from datetime import UTC, datetime, timedelta

from hub2hub.adapters.system_clock import SystemClock


def test_now_returns_utc_datetime_close_to_real_time() -> None:
    before = datetime.now(UTC)
    got = SystemClock().now()
    after = datetime.now(UTC)

    assert before - timedelta(seconds=1) <= got <= after + timedelta(seconds=1)
    assert got.tzinfo is not None
