from __future__ import annotations

from houba.domain.scan.gate import GateAction, decide_gate
from houba.domain.scan.summary import Severity

_CRIT = {"vuln.critical": "1", "vuln.high": "0", "vuln.medium": "0", "vuln.low": "0"}
_HIGH = {"vuln.critical": "0", "vuln.high": "2", "vuln.medium": "0", "vuln.low": "0"}
_CLEAN = {"vuln.critical": "0", "vuln.high": "0", "vuln.medium": "0", "vuln.low": "0"}


def test_critical_blocks_when_enforce_critical() -> None:
    assert (
        decide_gate(_CRIT, enforce_from=Severity.critical, audit_from=Severity.high)
        == GateAction.block
    )


def test_high_audits_when_enforce_critical_audit_high() -> None:
    assert (
        decide_gate(_HIGH, enforce_from=Severity.critical, audit_from=Severity.high)
        == GateAction.audit
    )


def test_clean_passes() -> None:
    assert (
        decide_gate(_CLEAN, enforce_from=Severity.critical, audit_from=Severity.high)
        == GateAction.clean
    )


def test_no_thresholds_is_clean() -> None:
    assert decide_gate(_CRIT, enforce_from=None, audit_from=None) == GateAction.clean


def test_enforce_only_no_audit() -> None:
    """When only enforce_from is set, block fires but audit never fires."""
    assert decide_gate(_CRIT, enforce_from=Severity.critical, audit_from=None) == GateAction.block
    assert decide_gate(_HIGH, enforce_from=Severity.critical, audit_from=None) == GateAction.clean


def test_audit_only_no_enforce() -> None:
    """When only audit_from is set, nothing can block — only audit or clean."""
    assert decide_gate(_CRIT, enforce_from=None, audit_from=Severity.high) == GateAction.audit
    assert decide_gate(_CLEAN, enforce_from=None, audit_from=Severity.high) == GateAction.clean
