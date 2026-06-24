from datetime import timedelta

import pytest

from houba.domain.verify import Requirement, parse_duration, parse_requirements
from houba.errors import ConfigError


@pytest.mark.parametrize(
    "text,expected",
    [("7d", timedelta(days=7)), ("12h", timedelta(hours=12)),
     ("30m", timedelta(minutes=30)), ("45s", timedelta(seconds=45))],
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
        Requirement.scan_pass, Requirement.stamp, Requirement.sbom
    }


def test_parse_requirements_rejects_unknown():
    with pytest.raises(ConfigError):
        parse_requirements("scan-pass,bogus")


from datetime import datetime, timezone

from houba.domain.scan.summary import Severity
from houba.domain.verify import VerifyReport, evaluate

NOW = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)


def _eval(reqs, **kw):
    base = dict(
        stamp_present=False, sbom_present=False, scan_predicates=[],
        max_severity=Severity.high, max_age=timedelta(days=7), now=NOW,
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
