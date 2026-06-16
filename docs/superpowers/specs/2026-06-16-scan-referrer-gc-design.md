# Scan-referrer garbage collection (`houba gc`) — design

*Status: design. Date: 2026-06-16.*

## Problem

Every `houba attach` call writes a fresh scan-result referrer
(`application/vnd.houba.scan.result.v1`) onto the subject image. Re-scanning the
same image — the normal cadence as new CVEs land and CI re-runs — accumulates
referrers without bound. Old scan results are *superseded* the moment a newer
scan of the same kind lands, yet nothing ever removes them. This is the last
remaining feature-side item on the roadmap (*Now — Scan-referrer GC*): it
matters once `attach` volume grows.

houba is a stamper, and the scan stamp is part of the product surface. GC keeps
that surface clean: a subject should carry the *current* scan signal per scanner,
not an ever-growing archive of stale ones.

## Goals

- A scheduled, catalog-walking command that removes **superseded** scan-result
  referrers across the registry roster.
- Retention is **per `(tool, format)`** group: a Trivy vulnerability scan and a
  `regis` posture report on the same subject never reap each other; only repeat
  runs of the *same* scanner+format are collected.
- Retention rule reuses the existing tag-retention model: **keep the N newest per
  group AND only collect those older than `older_than_days`** (both conditions).
- Dry-run by default; `--apply` to delete. Per-subject failures redden the exit
  code without blocking siblings.
- Registry-config parity with `reconcile` / `audit` / `purge` / `attach`
  (`HOUBA_REGISTRIES` roster + `--registry` override).

## Non-goals (v1)

- **Reaping the paired cosign attestation.** cosign attaches the attestation to
  the *subject digest*, not to the scan referrer; the only link to the report it
  covers is the `report_digest` buried in its signed predicate. Correlating
  requires reading/parsing each attestation's DSSE predicate — a materially
  larger lift. v1 collects `scan.result.v1` referrers only. **Known limitation:**
  a collected report can leave an orphan attestation pointing at a gone report.
  Tracked as a follow-up.
- **Concurrent / sharded walk.** Sequential in v1, exactly like `purge`.
- **Per-policy retention.** Thresholds are global CLI flags, not `MirrorPolicy`
  fields. GC sweeps registry state, it does not load policies (like `purge` /
  `audit`).

## Architecture (hexagonal)

No new port. `RegistryPort` already exposes `list_referrers(ref, artifact_type)`
and `delete_referrer(ref)`. GC is a recomposition of existing primitives — the
twin of `purge`'s walk, minus the usage oracle (the decision is purely
temporal/local, so it is 100 % pure domain — no fail-closed on an external
service).

```
cli/gc.py (Typer, thin)
  → use_cases/gc.py        (orchestration: catalog walk + delete)
       → domain/scan/gc.py (PURE: decides what to collect)
       ↘ ports/RegistryPort (list_repositories / list_tags / list_referrers / delete_referrer)
```

### Run flow

1. Resolve targets: the full roster, or a single registry when `--registry` is given.
2. Per registry → `ensure_registry_session` (shared login) → `list_repositories`
   → `list_tags` → for each `repo:tag`, `list_referrers(image_ref, SCAN_RESULT_ARTIFACT_TYPE)`.
3. Pass the `Referrer` list (with annotations) to the **pure domain** function,
   which returns the digests to collect.
4. `--apply`: `delete_referrer(f"{repo_ref}@{digest}")` for each. Dry-run: report
   the candidates without deleting.
5. Aggregate a `GcReport` (per subject: kept / collected / errors), with the exit
   code derived as in `purge`.

## Domain core — `houba/domain/scan/gc.py` (pure)

All decision logic lives here; testable without I/O, under the 90 % `domain`
coverage bar.

```python
def select_superseded_referrers(
    referrers: list[Referrer],
    *,
    keep: int,
    older_than: timedelta,
    now: datetime,
    prefix: str,
) -> list[str]:  # referrer digests to collect
```

Algorithm:

1. **Parse** each referrer → `(tool, format, timestamp)` from its annotations
   `{prefix}.scan.tool`, `{prefix}.scan.format`, `{prefix}.scan.timestamp`.
2. **Fail-safe**: any referrer whose timestamp cannot be read as a valid ISO
   datetime (annotation missing/unparseable, or empty `prefix`) is **ignored →
   never collected**. We only delete what we understand.
3. **Group** by `(tool, format)`.
4. Within each group, **reuse `select_retention_excess`** from
   `domain/retention.py` (the same keep-N + older-than model already proven on
   tags): the "key" passed is the referrer digest, the "date" is its
   `scan.timestamp`. The newest of each group is protected mechanically by the
   ranking.
5. Return the flat list of digests to collect, sorted (deterministic).

A private `_ParsedReferrer(digest, tool, format, timestamp)` dataclass stays
module-local. Dependency `domain/scan/gc.py → domain/retention.py` is
domain→domain, allowed.

## Use case — `houba/use_cases/gc.py`

Twin of `purge`'s walk, without the oracle.

```python
class GcOutcome(BaseModel):
    image_ref: str
    kept: int                 # referrers retained for this subject
    collected: list[str]      # digests collected (or candidates, in dry-run)
    applied: bool = False
    error: ErrorInfo | None = None

class GcReport(BaseModel):
    mode: Literal["apply", "dry-run"]
    outcomes: list[GcOutcome]

def gc_exit_code(report: GcReport) -> int:   # 0 else worst error exit code — mirrors purge_exit_code
def gc_referrers(*, registry, roster, only_registry, label_prefix,
                 keep, older_than_days, now, apply) -> GcReport
```

- Walk: `targets` (roster or `--registry`) → `ensure_registry_session` (shared
  login) → `list_repositories` → `list_tags` → `list_referrers(ref, SCAN_RESULT_ARTIFACT_TYPE)`.
- Per subject: call `select_superseded_referrers(...)`, then under `--apply` a
  `delete_referrer` loop. A per-subject error is captured in `error` (reddens the
  exit, never blocks siblings).
- `SCAN_RESULT_ARTIFACT_TYPE` is promoted to a shared constant under `domain/scan`
  (today it lives in `attach.py`) so `attach` and `gc` share it without a
  use-case→use-case coupling.

## CLI — `houba/cli/gc.py` (thin)

Flags: `--registry`, `--keep` (default 2), `--older-than-days` (default 30),
`--apply` (dry-run by default), `--log-format`. Builds the composition root via
`_di.py`, calls `gc_referrers`, renders the report via `cli/render.py`, maps the
exit code. New verb in the lineup: `reconcile · purge · attach · audit · version · gc`.

No new env var: thresholds are flags; everything else is driven by the existing
`HOUBA_REGISTRIES` / `HOUBA_LABEL_PREFIX`.

## Errors & exit codes

Reuse the established hierarchy. Per-subject `HoubaError` is captured into
`GcOutcome.error` via the shared `ErrorInfo(type, message, exit_code_for(exc))`
pattern; `gc_exit_code` returns the worst per-candidate exit code, else 0 — a
direct copy of `purge_exit_code`.

## Testing (strict TDD, one behavior per commit)

- **Unit domain** (`tests/unit/domain/scan/test_gc.py`): grouping by
  `(tool, format)`; keep-N honored; older-than guard; unparseable referrers
  ignored; empty prefix ⇒ nothing collected; sort determinism. The bulk of the
  tests (pure logic).
- **Unit use case** (`tests/unit/use_cases/test_gc.py`): on `FakeRegistryPort`
  (already journals deletions and seeds referrers) — multi-registry walk; dry-run
  deletes nothing; `--apply` deletes the right digests; `--registry` narrows the
  target; a per-subject error reddens the exit without blocking siblings.
- **Integration CLI** (`tests/integration/test_cli_gc.py`): fake-bin `regctl`
  with a "multiple scan-referrers" scenario; assert on the `delete`/`referrer`
  argv and the exit code.

## Documentation & C4 sync (same change, per CLAUDE.md)

- **C4**: `workspace.dsl` — add the `gc` use-case component to the **Component** /
  **Hexagon** views; refresh the Mermaid exports under `docs/architecture/_export/`.
- **ADR**: thin `docs/architecture/decisions/0028-scan-referrer-gc.md` linking to
  this spec.
- **Examples**: a short `docs/examples/` page showing `houba gc` (dry-run vs
  `--apply`) plus the README walkthrough.
- **Roadmap**: move "Scan-referrer GC" from *Now* to *Delivered* in
  `docs/roadmap.md`.
- **Schemas/CLI**: no new Pydantic policy model (thresholds are flags), so no
  JSON Schema regeneration — just the verb's documentation.
