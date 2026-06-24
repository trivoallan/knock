from datetime import UTC, datetime, timedelta

import pytest

from houba.domain.scan.summary import Severity
from houba.domain.verify import Requirement, evaluate, parse_duration, parse_requirements
from houba.errors import ConfigError
from houba.ports.attestor import VerifiedPredicate


@pytest.mark.parametrize(
    "text,expected",
    [
        ("7d", timedelta(days=7)),
        ("12h", timedelta(hours=12)),
        ("30m", timedelta(minutes=30)),
        ("45s", timedelta(seconds=45)),
    ],
)
def test_parse_duration_units(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("bad", ["", "7", "7x", "d", "-3d", "1.5h"])
def test_parse_duration_rejects_garbage(bad):
    with pytest.raises(ConfigError):
        parse_duration(bad)


def test_parse_requirements_default_and_subset():
    assert parse_requirements("scan-pass") == {Requirement.scan_pass}
    assert parse_requirements("scan-pass,stamp,sbom") == {
        Requirement.scan_pass,
        Requirement.stamp,
        Requirement.sbom,
    }


def test_parse_requirements_rejects_unknown():
    with pytest.raises(ConfigError):
        parse_requirements("scan-pass,bogus")


NOW = datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)


def _eval(reqs, **kw):
    base = dict(
        stamp_present=False,
        sbom_present=False,
        scan_predicates=[],
        max_severity=Severity.high,
        max_age=timedelta(days=7),
        now=NOW,
    )
    base.update(kw)
    return evaluate(requirements=reqs, **base)


def test_evaluate_reports_only_requested_requirements():
    report = _eval({Requirement.stamp}, stamp_present=True)
    assert [o.requirement for o in report.outcomes] == [Requirement.stamp]
    assert report.passed is True


def test_evaluate_stamp_absent_fails():
    report = _eval({Requirement.stamp}, stamp_present=False)
    assert report.passed is False
    assert report.outcomes[0].passed is False
    assert "stamp" in report.outcomes[0].detail


def test_evaluate_sbom_present_passes_absent_fails():
    assert _eval({Requirement.sbom}, sbom_present=True).passed is True
    assert _eval({Requirement.sbom}, sbom_present=False).passed is False


def test_evaluate_combines_requirements():
    report = _eval({Requirement.stamp, Requirement.sbom}, stamp_present=True, sbom_present=False)
    assert report.passed is False
    assert {o.requirement for o in report.outcomes} == {Requirement.stamp, Requirement.sbom}


def _pred(at, **vuln):
    return VerifiedPredicate(summary={f"vuln.{k}": str(v) for k, v in vuln.items()}, attested_at=at)


def test_scan_pass_fresh_and_clean():
    p = _pred("2026-06-24T11:00:00+00:00", critical=0, high=0)
    assert _eval({Requirement.scan_pass}, scan_predicates=[p]).passed is True


def test_scan_pass_fails_on_severity():
    p = _pred("2026-06-24T11:00:00+00:00", critical=1)
    out = _eval({Requirement.scan_pass}, scan_predicates=[p]).outcomes[0]
    assert out.passed is False and "critical" in out.detail


def test_scan_pass_fails_closed_when_no_predicate():
    out = _eval({Requirement.scan_pass}, scan_predicates=[]).outcomes[0]
    assert out.passed is False and "no verifiable scan attestation" in out.detail


def test_scan_pass_fails_on_stale():
    p = _pred("2026-06-01T00:00:00+00:00", high=0)  # > 7d before NOW
    out = _eval({Requirement.scan_pass}, scan_predicates=[p]).outcomes[0]
    assert out.passed is False and "SLA" in out.detail


def test_scan_pass_picks_freshest_predicate():
    old_bad = _pred("2026-06-01T00:00:00+00:00", critical=1)
    new_good = _pred("2026-06-24T11:30:00+00:00", critical=0, high=0)
    assert _eval({Requirement.scan_pass}, scan_predicates=[old_bad, new_good]).passed is True


def test_scan_pass_fails_closed_on_unparseable_attested_at():
    out = _eval({Requirement.scan_pass}, scan_predicates=[_pred("not-a-date", high=0)]).outcomes[0]
    assert out.passed is False and "unparseable" in out.detail


def test_stamp_absent_detail_has_fix_hint():
    out = _eval({Requirement.stamp}, stamp_present=False).outcomes[0]
    assert out.passed is False and "houba reconcile" in out.detail


def test_sbom_absent_detail_has_fix_hint():
    out = _eval({Requirement.sbom}, stamp_present=True, sbom_present=False).outcomes[0]
    assert out.passed is False and "houba reconcile" in out.detail


def test_scan_absent_detail_has_fix_hint():
    out = _eval(
        {Requirement.scan_pass}, stamp_present=True, sbom_present=True, scan_predicates=[]
    ).outcomes[0]
    assert out.passed is False and "houba attach" in out.detail
