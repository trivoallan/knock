from __future__ import annotations

from datetime import UTC, datetime

import pytest

from knock.domain.lifecycle import MarkIdentity
from knock.errors import UsageOracleError
from knock.ports.usage_oracle import UsageQuery
from tests.fakes.usage_oracle import FakeUsageOraclePort


def _q(digest: str) -> UsageQuery:
    return UsageQuery(
        digest=digest,
        image_ref="h/r:t",
        identity=MarkIdentity(policy="p", import_="i", variant="v"),
        since=datetime(2026, 5, 29, tzinfo=UTC),
    )


def test_fake_returns_seeded_last_seen_and_journals() -> None:
    seen = datetime(2026, 6, 10, tzinfo=UTC)
    oracle = FakeUsageOraclePort(last_seen={"sha256:aaa": seen})
    assert oracle.last_prod_usage(_q("sha256:aaa")).last_seen == seen
    assert oracle.last_prod_usage(_q("sha256:bbb")).last_seen is None
    assert [q.digest for q in oracle.queried] == ["sha256:aaa", "sha256:bbb"]


def test_fake_can_raise() -> None:
    oracle = FakeUsageOraclePort(fail={"sha256:boom"})
    with pytest.raises(UsageOracleError):
        oracle.last_prod_usage(_q("sha256:boom"))
