# `houba attach --fail-on <severity>` — design

*Status: design. Roadmap item: **Now → "Let the front door say no"**. Date: 2026-06-15.*

## Why

The single-front-door mandate is confirmed; *coverage gates value* now needs an **enforcement lever**.
Today `houba attach` only *observes* — it ingests a scan report, attaches it as a signed OCI referrer,
and always exits 0. `--fail-on <severity>` turns that ingestion into a **CI gate**: the front door can
say *no*. It is the first step from "we record provenance" to "we block what fails policy".

## The rule

`attach` stays **observational by default**. With `--fail-on <severity>`, after the normal ingestion
(referrer attached, attestation signed when configured — all unchanged), houba exits **1** when the
scan contains at least one finding **at the given severity or above**, else **0**. The gate never
changes what is attached — it only influences the exit code. This mirrors the established
`audit --fail-on-uncovered` pattern (`use_cases/audit.py:audit_exit_code` → `cli/audit.py` →
`raise typer.Exit(code)`).

Severity order (highest → lowest): **critical > high > medium > low > unknown**. All five are valid
`--fail-on` targets. `--fail-on low` trips on `low` *and* `unknown`; `--fail-on unknown` trips on any
finding at all (no blind spot — chosen so an unscored CVE can't silently pass a gate).

## 1. Domain — canonical severity + gate decision (pure, `domain/scan/`)

- A `Severity` `str`-Enum (`critical/high/medium/low/unknown`) plus one canonical order. This becomes
  the **single source of truth** for severity ranking; the SARIF mapper's private `_BUCKETS` tuple
  (`domain/scan/formats/sarif.py`) is refactored to derive from it — removing the duplicated ordering
  (a targeted DRY cleanup of code this feature touches).
- A pure function `gate_breached(facts: dict[str, str], fail_on: Severity) -> bool`: sums the
  `vuln.<bucket>` counts for every bucket ranked **at or above** `fail_on`; returns `True` when the sum
  is > 0. Counts are parsed defensively (a non-integer value counts as 0).

## 2. Use case + CLI

- `use_cases/attach.py` — `attach_exit_code(outcome: ScanOutcome, *, fail_on: Severity | None) -> int`,
  mirroring `audit_exit_code`: returns `1` when `fail_on` is set and `gate_breached(outcome.facts,
  fail_on)`, else `0`. `attach_scan` is **unchanged** — the gate reads `ScanOutcome.facts`, which
  already carries the per-severity counts.
- `cli/attach.py` — a `--fail-on` option typed as `Severity` (typer validates the value set and shows
  it in `--help`); after `render_scan_outcome(...)`, `raise typer.Exit(attach_exit_code(outcome,
  fail_on=fail_on))`. On a breach, emit one concise stderr line (e.g. `fail-on high: 6 finding(s) at or
  above — gating`) so a CI log explains the non-zero exit.

## 3. Edges / scope (assumed)

- **Formats without `vuln.*` facts** (future EOL/`regis`, non-CVE CycloneDX): no buckets → never a
  breach → exit 0. `--fail-on` is vuln-severity semantics; documented. Only SARIF exists today.
- **No `--fail-on`**: behaviour is strictly unchanged (exit 0, observational).
- **No count threshold** (e.g. "fail on ≥ 5 highs") — severity-level threshold only (YAGNI).

## 4. Testing (TDD)

- **Domain (`tests/unit/domain`, ≥ 90 %):** the canonical order; `gate_breached` at each threshold
  (at-or-above; `unknown` counted under `low` and `unknown`; all-zero counts → no breach; facts with no
  `vuln.*` keys → no breach; non-integer count → treated as 0); the SARIF mapper still emits the same
  `vuln.<bucket>` facts after the `_BUCKETS` refactor.
- **Use case:** `attach_exit_code` → 1 on breach, 0 otherwise and when `fail_on is None`.
- **Integration CLI (fake-bin):** `attach --fail-on critical` exits 1 when the report has a critical
  finding, 0 when it does not; without `--fail-on`, always 0; an invalid `--fail-on` value is rejected
  by typer (usage error).

## 5. Docs to sync (same change)

- ADR mirror under `docs/architecture/decisions/` linking this spec.
- C4 model: **unchanged** — no new port/adapter/actor (a CLI flag + a domain severity concept).
- `docs/examples/`: the `attach` walkthrough gains a `--fail-on` CI-gate example.
- `CLAUDE.md`: the CLI verb list is unchanged, but note `attach` gained `--fail-on`.
- Roadmap: tick the *Now* "Let the front door say no" item when shipped.
