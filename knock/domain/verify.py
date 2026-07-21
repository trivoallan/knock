"""Pure verdict logic for `knock verify` — the read-side gate over knock's referrers.

No I/O, no config, no clock of its own: the use case resolves facts (annotations,
referrers, verified predicates) and the clock, and passes them in. Reuses
`gate_breached` so the severity semantics are identical to `attach --fail-on`.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from knock.domain.scan.summary import Severity, gate_breached
from knock.errors import ConfigError
from knock.ports.attestor import VerifiedPredicate


class Requirement(enum.StrEnum):
    stamp = "stamp"
    scan_pass = "scan-pass"  # noqa: S105
    sbom = "sbom"


_DURATION_RE = re.compile(r"^(\d+)([dhms])$")
_UNIT = {"d": "days", "h": "hours", "m": "minutes", "s": "seconds"}


def parse_duration(text: str) -> timedelta:
    """`"7d" | "12h" | "30m" | "45s"` -> timedelta. Anything else -> ConfigError."""
    m = _DURATION_RE.match(text)
    if not m:
        raise ConfigError(f"invalid --max-age {text!r}; use forms like 7d, 12h, 30m, 45s")
    return timedelta(**{_UNIT[m.group(2)]: int(m.group(1))})


def parse_requirements(text: str) -> set[Requirement]:
    """Comma-separated subset of the Requirement values. Unknown token -> ConfigError."""
    out: set[Requirement] = set()
    for token in (t.strip() for t in text.split(",") if t.strip()):
        try:
            out.add(Requirement(token))
        except ValueError:
            allowed = ", ".join(r.value for r in Requirement)
            raise ConfigError(f"unknown --require {token!r}; allowed: {allowed}") from None
    if not out:
        allowed = ", ".join(r.value for r in Requirement)
        raise ConfigError("--require must name at least one of: " + allowed)
    return out


@dataclass(frozen=True)
class RequirementOutcome:
    requirement: Requirement
    passed: bool
    detail: str


@dataclass(frozen=True)
class VerifyReport:
    outcomes: tuple[RequirementOutcome, ...]

    @property
    def passed(self) -> bool:
        return all(o.passed for o in self.outcomes)


def _stamp_outcome(present: bool) -> RequirementOutcome:
    return RequirementOutcome(
        Requirement.stamp,
        present,
        "knock stamp present" if present else "no knock stamp on the manifest",
    )


def _sbom_outcome(present: bool) -> RequirementOutcome:
    return RequirementOutcome(
        Requirement.sbom,
        present,
        "SBOM referrer present" if present else "no SBOM referrer",
    )


def _to_utc(text: str) -> datetime:
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _scan_outcome(
    preds: list[VerifiedPredicate], max_severity: Severity, max_age: timedelta, now: datetime
) -> RequirementOutcome:
    if not preds:
        return RequirementOutcome(Requirement.scan_pass, False, "no verifiable scan attestation")
    try:
        freshest = max(preds, key=lambda p: _to_utc(p.attested_at))
        age = now - _to_utc(freshest.attested_at)
    except ValueError:
        # A signed predicate with a non-ISO attested_at can't establish freshness. The gate's
        # posture is fail-closed, so reject rather than let ValueError escape the pure domain
        # (it would surface as exit 4 InternalError instead of a clean exit-1 gate verdict).
        return RequirementOutcome(
            Requirement.scan_pass,
            False,
            "scan attestation has an unparseable attested_at timestamp",
        )
    if gate_breached(freshest.summary, max_severity):
        breached = [
            f"{n} finding(s) at {s.value}"
            for s in Severity
            if (n := int(freshest.summary.get(f"vuln.{s.value}", "0") or "0")) > 0
            and gate_breached({f"vuln.{s.value}": str(n)}, max_severity)
        ]
        return RequirementOutcome(
            Requirement.scan_pass, False, f"{'; '.join(breached)} (>= {max_severity.value})"
        )
    if age > max_age:
        return RequirementOutcome(
            Requirement.scan_pass,
            False,
            f"scan attested {int(age.total_seconds())}s ago > {int(max_age.total_seconds())}s SLA",
        )
    return RequirementOutcome(
        Requirement.scan_pass,
        True,
        f"severity <= {max_severity.value}, attested {int(age.total_seconds())}s ago",
    )


def evaluate(
    *,
    requirements: set[Requirement],
    stamp_present: bool,
    sbom_present: bool,
    scan_predicates: list[VerifiedPredicate],
    max_severity: Severity,
    max_age: timedelta,
    now: datetime,
) -> VerifyReport:
    outcomes: list[RequirementOutcome] = []
    if Requirement.stamp in requirements:
        outcomes.append(_stamp_outcome(stamp_present))
    if Requirement.scan_pass in requirements:
        outcomes.append(_scan_outcome(scan_predicates, max_severity, max_age, now))
    if Requirement.sbom in requirements:
        outcomes.append(_sbom_outcome(sbom_present))
    return VerifyReport(outcomes=tuple(outcomes))
