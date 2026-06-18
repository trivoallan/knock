"""Pure per-destination gate decision over scan facts (reuses gate_breached)."""

from __future__ import annotations

import enum

from houba.domain.scan.summary import Severity, gate_breached


class GateAction(enum.StrEnum):
    block = "block"  # Enforce breached — do not publish
    audit = "audit"  # Audit breached — publish but warn
    clean = "clean"  # publish, no finding above any threshold


def decide_gate(
    facts: dict[str, str], *, enforce_from: Severity | None, audit_from: Severity | None
) -> GateAction:
    if enforce_from is not None and gate_breached(facts, enforce_from):
        return GateAction.block
    if audit_from is not None and gate_breached(facts, audit_from):
        return GateAction.audit
    return GateAction.clean
