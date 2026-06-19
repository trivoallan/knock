# SARIF `kind` → governance verdicts (`policy.*`) — houba-core classification — design

Date: 2026-06-19
Status: Approved (brainstorm)

## Goal

Make houba's `SarifMapper` classify a SARIF **evaluation outcome** (a policy verdict) apart from a
**vulnerability finding**, using the standard SARIF `result.kind` as the agnostic discriminator —
never the producing tool's name. Verdicts land in a new severity-bucketed `policy.*` fact-space;
findings keep the existing `vuln.*` space. This is the first decomposed piece of the
"demo with regis to prove analyzer-agnosticism" effort; it is a houba-core domain change that
merges and tests independently of regis.

## Why now (the regis #789 finding)

regis PR #789 adds a `--sarif` output that emits **verdicts** (not raw findings): each policy breach
becomes a SARIF `result` carrying a `security-severity` (mapped from the verdict level) and a
`regis-level` property — but **no `kind`, no taxonomy**. Two problems this surfaces:

1. **Today's mapper miscounts verdicts as vulnerabilities.** `_classify` scores *before* it looks at
   `kind`: any result with a `security-severity` is bucketed into `vuln.<severity>` even if it also
   carries a `kind`. A governance verdict at CVSS 9.0 would inflate `vuln.critical`.
2. **`rule.*` is too coarse for governance.** The existing `kind` path collapses to a binary
   `rule.passed` / `rule.failed`, discarding the verdict's severity — so a "license: GPL in a
   proprietary image" critical and a "label hygiene" low look identical.

The fix is a houba↔producer **convention** plus a mapper reordering. regis emitting `kind` is a
parallel sibling-repo change (#789 follow-up); this spec does not depend on it (synthetic SARIF
fixtures exercise the new path).

## The convention (houba↔producer contract)

- A SARIF `result.kind` (`pass` / `fail` / `open` / `review` / …) marks an **evaluation outcome** →
  a governance verdict → routed to `policy.*`.
- A result **without** `kind` is a **finding** → `vuln.*` (unchanged; what grype/trivy emit).

houba keys on `kind` (standard SARIF semantics), **never on `tool.driver.name`** — that is what keeps
it analyzer-agnostic. A producer opts into governance bucketing by emitting `kind`.

## Design

### `_classify` — `kind` first (`houba/domain/scan/formats/sarif.py`)

Invert the current order so `kind` is checked **before** `security-severity`:

```python
def _classify(result, severities):
    kind = result.get("kind")
    if kind is not None:                       # evaluation outcome → governance verdict
        if kind == "pass":
            return "policy.passed"
        score = _result_score(result, severities)          # security-severity, rule fallback
        if score is not None:
            return f"policy.{_score_to_bucket(score)}"
        return f"policy.{_level_to_bucket(result.get('level'))}"
    # no kind → a finding (existing behavior)
    score = _result_score(result, severities)
    if score is not None:
        return f"vuln.{_score_to_bucket(score)}"
    return f"vuln.{_level_to_bucket(result.get('level'))}"
```

- `_result_score(result, severities)` extracts the existing logic: `properties.security-severity`,
  else the rule-level `severities[ruleId]`.
- `_level_to_bucket(level)` extracts the existing level fallback: `error`→`high`, `warning`→`medium`,
  `note`/`none`→`low`, else `unknown`.
- `_score_to_bucket` is unchanged (≥9 critical, ≥7 high, ≥4 medium, else low).

Result: a regis verdict (`kind: fail`, security-severity 9.0) → `policy.critical`; a grype CVE
(no `kind`, security-severity) → `vuln.critical`. Same mapper, split by a standard SARIF signal.

### Fact-space — `policy.<severity>` replaces `rule.*`

```python
fact_keys = (*(f"vuln.{b}" for b in _BUCKETS),
             *(f"policy.{b}" for b in _BUCKETS),
             "policy.passed")
# _BUCKETS = SEVERITY_VALUES = critical, high, medium, low, unknown
```

- `policy.<severity>` reuses the same `Severity` names as `vuln.*` (no new enum). Verdicts are
  bucketed by their severity, preserving it for a future governance view (the demo's POLICY column).
- `policy.passed` counts `kind: pass` results (regis emits breaches only, so 0 from regis today; the
  convention still supports passes from other producers).
- **`rule.passed` / `rule.failed` are removed**, superseded by `policy.*`. This changes the
  annotation keys `io.houba.scan.rule.*` → `io.houba.scan.policy.*` — a breaking change, acceptable
  in 0.x where `rule.*` was a near-unused posture affordance (no producer emitted it yet).

### What flows for free

- `build_scan_annotations` already emits `{prefix}.scan.<fact>` per fact → `io.houba.scan.policy.*`
  appear automatically.
- `ScanPredicate.summary` is an open `dict[str, str]` → **no schema change, no `make reference`**.
- `gate_breached` operates on `vuln.*` only → **unchanged**: `attach --fail-on` keeps gating on
  vulnerabilities; governance verdicts are reported in the stamp, not gated (consistent with today's
  posture behavior).

## Tests (domain, coverage gate ≥ 90 %)

Synthetic SARIF fixtures in the `SarifMapper` tests:

- `kind: fail` + `security-severity: 9.0` → `policy.critical` (**not** `vuln.*`) — the agnosticism
  proof, no tool name involved.
- no `kind` + `security-severity` → `vuln.<bucket>` (grype/trivy non-regression).
- `kind: pass` → `policy.passed`.
- `kind: fail`, no severity → `level` fallback → `policy.<bucket>`.
- Existing tests asserting `rule.passed` / `rule.failed` → migrated to `policy.*`.

## Docs ripple (grep `rule.passed` / `rule.failed` at implementation)

- `docs/how-to/attach-scan.md` — the "Posture reports" section references
  `io.houba.scan.rule.passed` / `rule.failed` and states a CVSS-scored result is always a vuln; rewrite
  to `policy.<severity>` + the `kind`-first convention (a `kind`-bearing result is a verdict regardless
  of its score).
- Any other doc/fixture/ADR mentioning `rule.passed` / `rule.failed` → migrate to `policy.*`.

## ADR

A thin ADR `docs/architecture/decisions/0039-sarif-kind-discriminates-policy-from-vuln.md` mirroring
this spec ("SARIF `kind` discriminates a governance verdict (`policy.*`) from a vulnerability finding
(`vuln.*`)"). 0039 is free on `main` (the scanstep ADR 0039 was on the closed #163 branch, never
merged) — confirm at implementation.

## Out of scope

- **C4 `workspace.dsl`** — unchanged: a domain refinement, no new port/adapter/actor/external system.
- **`blast-radius.sh` POLICY column** and **regis in `scan-attach.sh`** — the *demo* sub-project (next),
  not houba-core.
- **regis emitting `kind`** — a parallel sibling-repo change (#789 follow-up); this spec is testable
  without it via synthetic fixtures.
- **`make reference` / schema changes** — none (`summary` is an open dict).

## Acceptance

- `uv run pytest tests/unit/domain` green, `houba.domain` coverage ≥ 90 %.
- A `kind`-bearing SARIF result is counted in `policy.<severity>` (or `policy.passed`), never in
  `vuln.*`; a `kind`-less result keeps its `vuln.*` bucketing.
- `io.houba.scan.policy.*` annotations appear on attached referrers; `io.houba.scan.rule.*` no longer
  emitted.
- `attach --fail-on` behavior unchanged (gates `vuln.*` only).
- `docs/how-to/attach-scan.md` and ADR 0039 reflect the convention; `mypy --strict` clean on
  `houba.domain`; no `workspace.dsl` / `make reference` drift.
