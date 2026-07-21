# Reconcile output redesign

**Status:** Design approved — ready for implementation planning
**Date:** 2026-06-11
**Scope:** Replace the single-line `reconcile` summary with a structured, two-stream output, and make the reconciler resilient (accumulate-and-continue per policy).

## Problem

`knock reconcile` currently emits exactly one line:

```
reconcile: imported=3 updated=1 deleted=0 aliased=2
```

Gaps:

- No real-time progress — operations run silently, then a single line appears.
- No per-policy / per-variant / per-operation detail.
- The structlog infrastructure (`knock/logging.py`) exists but is **never wired** into the CLI; `KNOCK_LOG_FORMAT` / `KNOCK_LOG_LEVEL` are defined in config but unused.
- The apply phase is **fail-fast**: any registry exception aborts the whole run and short-circuits even the summary line (`knock/use_cases/reconcile.py:101-163`).

This serves none of the three jobs the output must do in CI: **debug post-mortem**, **change audit**, and **dry-run plan feedback**.

## Goals & constraints

- **Primary consumer:** non-interactive CI/CD (structured, parsable, traceable) — but a human must still be able to read both streams.
- **Three jobs served equally:** debug, audit, dry-run plan.
- **Two streams:**
  - **stdout** = structured *result* (machine contract).
  - **stderr** = *event journal* (structlog, verbosity-driven).
  - Both adapt to `KNOCK_LOG_FORMAT` (`text` → human-readable; `json` → machine).
- **Hierarchical result:** `run → policies → targets → variants → operations`, with aggregated counts at each level. JSON carries full detail; `text` stops at policy level by default, `--verbose` unfolds operations.
- **Accumulate-and-continue:** per-policy isolation; a failure marks the policy `failed` and the run continues; exit ≠ 0 if any failure.
- Respect the hexagonal layering (the reason knock exists): the journal is delivered through a **port**, not by coupling the use case to structlog.

## Architecture

### Approach: `Reporter` port for the in-flight journal (chosen over structlog-direct / no-events)

The use case receives a `Reporter` and emits events as work happens. A structlog-backed adapter renders the journal to stderr; a fake journals calls for tests. This keeps the use case pure-orchestration and 100% testable without capturing stderr, and follows the house pattern `port → fake → adapter → wire into _di.py`.

The stdout *result* is a rich return type rendered by the CLI — independent of the journal.

## Components

### 1. Result model — `knock/use_cases/report.py` (new)

**Pydantic** models (not dataclasses) so `model_json_schema()` can publish a schema of the report, consistent with the policy schema and the project's "JSON Schema wherever a declarative contract exists" rule.

```
RunReport
  ├─ mode            : "apply" | "dry-run"        # derived from dry_run_tags / dry_run_deletions
  ├─ totals          : Counts                      # imported/updated/deleted/aliased/skipped/failed
  ├─ status          : "ok" | "partial" | "failed"
  └─ policies        : list[PolicyReport]
       ├─ name, source, status ("ok" | "failed"), error: ErrorInfo | None
       ├─ totals      : Counts
       └─ targets     : list[TargetReport]          # one per destination
            ├─ dest_repo
            └─ variants : list[VariantReport]        # name, suffix, totals
                 └─ operations : list[Operation]
                        kind   : "imported" | "updated" | "deleted" | "aliased" | "skipped"
                        out_tag, src_tag?, digest?, applied: bool
```

- `applied: bool` distinguishes *executed* from *planned* → dry-run is served by the same structure (in `--dry-run`, every operation has `applied=false`).
- `skipped` (tag already up to date / within the 7-day digest-stability window) is **included** — exactly what the "why did nothing change?" debug job needs. Surfaced in JSON and under `--verbose`, not in the headline summary.
- `ErrorInfo` = `{type, message, exit_code}` where `exit_code` comes from `exit_code_for`.
- `Counts` is a reusable sub-model aggregated at run / policy / variant levels.

`RunReport` replaces `RunSummary`.

### 2. Error semantics — accumulate & continue

Isolation unit is the **policy**. The first operation that fails within a policy marks that policy `failed`, attaches `ErrorInfo`, **skips the remainder of that policy**, and moves to the next policy. The run always produces a complete `RunReport`.

- `RunReport.status`: `ok` (no failures) / `partial` (mixed) / `failed` (all failed).
- **Exit code:** derived by the CLI from the report. If ≥ 1 failure, exit = **max numeric** of the failures' `exit_code` values (4 ＞ 3 ＞ 2 ＞ 1 — worst wins, deterministic). In practice most are `AdapterError` → 2.
- `reconcile_policies` no longer raises on a per-policy apply failure; it continues.
- Errors **before** any mutation (alias-collision detection, config/registry resolution) stay **fail-fast** and propagate as today — they are plan errors, not apply errors, and there is nothing partial to report.

### 3. `Reporter` port + stderr journal — `knock/ports/reporter.py` (new)

`typing.Protocol` plus frozen-dataclass event models alongside it (house convention: each port has a data model beside it).

```python
class Reporter(Protocol):
    def run_started(self, policy_count: int, *, mode: str) -> None: ...
    def policy_started(self, name: str, source: str) -> None: ...
    def operation_applied(self, ev: OperationEvent) -> None: ...   # policy, dest, variant, kind, out_tag, digest, applied
    def policy_failed(self, name: str, error: ErrorInfo) -> None: ...
    def policy_completed(self, name: str, totals: Counts) -> None: ...
    def run_completed(self, report: RunReport) -> None: ...
```

- **Adapter** `knock/adapters/structlog_reporter.py` (new): `StructlogReporter` binds `structlog.get_logger()`; each method emits one structured, timestamped event on **stderr**. Rendering is `text` (ConsoleRenderer) or `json` per `KNOCK_LOG_FORMAT`. No retry / network — purely an output adapter.
- **Fake** `tests/fakes/fake_reporter.py` (new): journals calls (`calls.operations`, `calls.failures`, …) so use-case tests assert "event X was emitted" without capturing stderr.
- The use case takes `reporter: Reporter` as a parameter and emits as it goes.

### 4. stdout rendering — `knock/cli/render.py` (new)

`render_report(report, *, fmt, verbose, stream=stdout)`:

- **`text`**: one readable block per policy
  (`✓ name  imported=2 updated=1 skipped=4` / `✗ name  FAILED: AdapterError: …`), then a totals line. `--verbose` unfolds targets / variants / operations.
- **`json`**: `report.model_dump_json()` — the full tree, stable contract, clean for `| jq`.
- **Stream separation:** result on **stdout**, journal on **stderr**, so `knock reconcile … 2>/dev/null | jq` stays pure.

### 5. Wiring & schema publication

- `knock/cli/main.py`: an `@app.callback` loads settings and calls `knock.logging.configure(format_=settings.log_format, level=settings.log_level)` **once** before any command. The `_run` wrapper stays for fail-fast plan errors.
- `knock/cli/_di.py`: instantiate `StructlogReporter` and inject it into `reconcile_policies` (excluded from coverage — it is wiring).
- `knock/cli/reconcile.py`: build the result, choose the exit code from `RunReport.status`, render via `render_report`. The `--verbose` flag is added here.
- **JSON Schema:** publish `RunReport.model_json_schema()` via the same mechanism as the policy schema, so CI consumers can validate the report.
- **C4:** no new actor / external system / integration (structlog is internal; no new outbound flow) → `workspace.dsl` **unchanged**. Verified explicitly.

## Testing (TDD, house conventions)

- **Use-case** (`tests/unit` / use-case tests with fakes): `FakeReporter` + a `FakeRegistry` that raises on policy #2 → assert policy 2 `failed`, policies 1 and 3 `ok`, `RunReport` complete, `status=partial`, correct events emitted, totals correct.
- **Domain:** unchanged — no new business logic in `domain/`; the 90% domain coverage gate is preserved.
- **Renderer** (`cli`): snapshot tests for `text` (default + `--verbose`) and `json`.
- **Adapter** `StructlogReporter` (integration): capture structlog output, verify structured fields in both `text` and `json` modes.
- **Schema:** stability test of `RunReport.model_json_schema()`.

## Decisions locked

- **Reporter port (Approach A)** for the in-flight journal — not structlog-direct, not post-hoc reprojection.
- **Two streams**: stdout = structured result, stderr = event journal; both driven by `KNOCK_LOG_FORMAT`.
- **Hierarchical, Pydantic result model** with per-level counts; `text` stops at policy by default, `--verbose` unfolds; full detail always in JSON.
- **Accumulate-and-continue**, isolation per **policy**; exit code = max numeric of failures' codes.
- **`skipped` included** in the report (JSON + `--verbose`), excluded from the headline summary.

## Out of scope

- Interactive TTY niceties (spinners, live progress bars) — the target is non-interactive CI; the structlog journal covers in-flight feedback.
- Changing the alias-collision / plan-phase fail-fast semantics (those stay as-is).
- Any change to the transform/rebuild path (Phase 6) — this work is on the copy path only.
