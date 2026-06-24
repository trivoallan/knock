"""Pure verdict logic for `houba verify` — the read-side gate over houba's referrers.

No I/O, no config, no clock of its own: the use case resolves facts (annotations,
referrers, verified predicates) and the clock, and passes them in. Reuses
`gate_breached` so the severity semantics are identical to `attach --fail-on`.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from houba.domain.scan.summary import Severity, gate_breached
from houba.errors import ConfigError
from houba.ports.attestor import VerifiedPredicate


class Requirement(enum.StrEnum):
    stamp = "stamp"
    scan_pass = "scan-pass"
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
        raise ConfigError("--require must name at least one of: " + ", ".join(r.value for r in Requirement))
    return out
