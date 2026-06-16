from __future__ import annotations

from datetime import UTC, datetime, timedelta

from houba.domain.scan.gc import select_superseded_referrers
from houba.ports.registry import Referrer

NOW = datetime(2026, 6, 16, tzinfo=UTC)
PREFIX = "io.houba"


def _ref(digest: str, *, tool: str, fmt: str, ts: datetime) -> Referrer:
    return Referrer(
        digest=digest,
        artifact_type="application/vnd.houba.scan.result.v1",
        annotations={
            f"{PREFIX}.scan.tool": tool,
            f"{PREFIX}.scan.format": fmt,
            f"{PREFIX}.scan.timestamp": ts.isoformat(),
        },
        subject_tag="redis:7.2.0",
    )


def test_keeps_newest_collects_older_within_group():
    refs = [
        _ref("sha256:old", tool="trivy", fmt="sarif", ts=NOW - timedelta(days=60)),
        _ref("sha256:new", tool="trivy", fmt="sarif", ts=NOW - timedelta(days=40)),
    ]
    out = select_superseded_referrers(
        refs, keep=1, older_than=timedelta(days=30), now=NOW, prefix=PREFIX
    )
    assert out == ["sha256:old"]


def test_groups_are_independent_per_tool_format():
    refs = [
        _ref("sha256:trivy-old", tool="trivy", fmt="sarif", ts=NOW - timedelta(days=60)),
        _ref("sha256:trivy-new", tool="trivy", fmt="sarif", ts=NOW - timedelta(days=40)),
        _ref("sha256:regis", tool="regis", fmt="sarif", ts=NOW - timedelta(days=90)),
    ]
    out = select_superseded_referrers(
        refs, keep=1, older_than=timedelta(days=30), now=NOW, prefix=PREFIX
    )
    # regis is alone in its group → protected; only the older trivy is collected.
    assert out == ["sha256:trivy-old"]


def test_older_than_guard_protects_recent_supersession():
    refs = [
        _ref("sha256:a", tool="trivy", fmt="sarif", ts=NOW - timedelta(days=2)),
        _ref("sha256:b", tool="trivy", fmt="sarif", ts=NOW - timedelta(days=1)),
    ]
    out = select_superseded_referrers(
        refs, keep=1, older_than=timedelta(days=30), now=NOW, prefix=PREFIX
    )
    assert out == []  # superseded, but not yet older than the grace window


def test_unparseable_or_missing_timestamp_is_ignored():
    good = _ref("sha256:good", tool="trivy", fmt="sarif", ts=NOW - timedelta(days=60))
    no_ts = Referrer(
        digest="sha256:nots",
        artifact_type="application/vnd.houba.scan.result.v1",
        annotations={f"{PREFIX}.scan.tool": "trivy", f"{PREFIX}.scan.format": "sarif"},
        subject_tag="redis:7.2.0",
    )
    bad_ts = Referrer(
        digest="sha256:bad",
        artifact_type="application/vnd.houba.scan.result.v1",
        annotations={
            f"{PREFIX}.scan.tool": "trivy",
            f"{PREFIX}.scan.format": "sarif",
            f"{PREFIX}.scan.timestamp": "not-a-date",
        },
        subject_tag="redis:7.2.0",
    )
    out = select_superseded_referrers(
        [good, no_ts, bad_ts], keep=1, older_than=timedelta(days=30), now=NOW, prefix=PREFIX
    )
    # `good` is alone among parseable refs → protected; unparseable ones never collected.
    assert out == []


def test_empty_prefix_collects_nothing():
    refs = [
        _ref("sha256:old", tool="trivy", fmt="sarif", ts=NOW - timedelta(days=60)),
        _ref("sha256:new", tool="trivy", fmt="sarif", ts=NOW - timedelta(days=40)),
    ]
    out = select_superseded_referrers(
        refs, keep=1, older_than=timedelta(days=30), now=NOW, prefix=""
    )
    assert out == []


def test_result_is_sorted_deterministically():
    refs = [
        _ref("sha256:zzz", tool="a", fmt="sarif", ts=NOW - timedelta(days=60)),
        _ref("sha256:kept-a", tool="a", fmt="sarif", ts=NOW - timedelta(days=10)),
        _ref("sha256:aaa", tool="b", fmt="sarif", ts=NOW - timedelta(days=60)),
        _ref("sha256:kept-b", tool="b", fmt="sarif", ts=NOW - timedelta(days=10)),
    ]
    out = select_superseded_referrers(
        refs, keep=1, older_than=timedelta(days=30), now=NOW, prefix=PREFIX
    )
    assert out == ["sha256:aaa", "sha256:zzz"]  # cross-group, sorted by digest
