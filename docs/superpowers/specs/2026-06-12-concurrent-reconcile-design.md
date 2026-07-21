# Concurrent reconcile — execution model

- **Date:** 2026-06-12
- **Status:** approved (design), not yet implemented. Amended 2026-06-12 for horizontal scale-out — see the [horizontal sharding spec](2026-06-12-horizontal-sharding-design.md).
- **Scope:** `use_cases/reconcile.py` orchestration + report model; one adapter (`structlog_reporter`); one config var; one CLI flag.

## Context & motivation

The `reconcile` path is fully sequential: `reconcile_policies` loops over policies, then
plans/destinations, then variants, then tags. Every expensive operation is I/O —
`registry.inspect`/`list_tags` (plan phase) and especially `builder.build_and_push`
(minutes per image), `registry.copy`, `registry.annotate` (apply phase).

This work is **anticipatory**: there is no measured latency pain today. The goal is therefore
**a clean, well-bounded concurrency model that respects the hexagonal architecture** — not the
optimisation of a specific hotspot. We want the boundary placed correctly now, so that turning on
parallelism is a local change. Scaling *across* policies is **not** an in-process concern: it is handled
by horizontal sharding across pods (see the [horizontal sharding spec](2026-06-12-horizontal-sharding-design.md)),
so per-pod execution stays single-policy-at-a-time by design.

## Goals

1. Parallelise the expensive apply-phase work where the time actually is — the per-tag/per-variant
   `build_and_push` / `copy` / `annotate` loop.
2. Keep `domain/` pure and the adapters untouched (except a lock in the reporter adapter).
3. Collect partial failures instead of aborting a whole policy on the first failing tag.
4. Make concurrency a bounded, configurable knob with a deterministic sequential fallback.
5. Stay compatible with horizontal scale-out: a pod threads *tags within a policy*; *policies* are scaled
   across pods by sharding, not by in-process threads.

## Non-goals

- Parallelising **across policies** in-process (sequential per pod *by design* — policies scale across
  pods via [sharding](2026-06-12-horizontal-sharding-design.md), not threads).
- Parallelising **across plans/destinations** within a policy (kept sequential in v1).
- Parallelising the **plan phase** reads (`inspect`/`list_tags`) — marginal payoff vs. build cost; out of scope.
- Rewriting adapters to `asyncio` — rejected (see *Decisions*).

## Decisions (with rejected alternatives)

| # | Decision | Rejected alternatives & why |
|---|----------|------------------------------|
| D1 | **Granularity: per tag/variant, policies sequential.** | *Per-policy*: zero gain on the common "1 image / N tags" case (the cost is intra-policy). *Plan-phase only*: lowest payoff. |
| D2 | **Primitive: `ThreadPoolExecutor` (bounded).** | *asyncio*: would force a rewrite of every adapter (`httpx` async, `asyncio.subprocess`) and the Reporter port — huge cost, nil benefit (work is already subprocess). *ProcessPoolExecutor*: builds/copies are already separate processes; adds pickling + reporting complexity for nothing. Threads give real parallelism because the subprocess/HTTP adapters release the GIL. |
| D3 | **Failure: continue & collect (partial).** | *Fail-fast*: preserves current semantics but loses per-tag visibility at incident time. We accept a richer report model in exchange for partial results. |
| D4 | **Limit: `KNOCK_MAX_CONCURRENCY` (default 4) + `--concurrency/-j` CLI override.** | *Default = `os.cpu_count()`*: risks saturating disk/network on a large runner, less predictable. *Config only (no flag)*: less ergonomic for tuning a single run. Builds are disk/network heavy → a low fixed default is safer. |
| D5 | **Reporter: thread-safe, interleaving accepted.** | *Buffer-and-flush ordered*: deterministic output but kills real-time feedback during multi-minute builds. Each event already carries `policy`/`variant`/`out_tag`, so interleaved lines stay attributable. |

## Architecture — scope & boundary

Concurrency lives **entirely in `use_cases/reconcile.py`** (the orchestration). `domain/` stays pure.
The subprocess/HTTP adapters (`skopeo`/`regctl`/`buildkit`) are unchanged. The only adapter touched is
`structlog_reporter` (a lock).

A single bounded `ThreadPoolExecutor` is created **once** in `reconcile_policies` and shared across the
run. Policies and plans iterate sequentially around it; only the tag-level stages inside a single plan's
apply fan out onto it. Scaling *policies* is done by running more pods (horizontal sharding), not by
submitting policies to this pool — so this pool stays a per-pod, tag-level device.

`max_concurrency == 1` ⇒ **no pool**: stages run as a direct `[fn(it) for it in items]` map, giving a
deterministic sequential code path for debugging.

## Execution model — a small DAG per plan

A single plan's apply (`_apply_plan`) becomes **three barriered stages**, flattening all variants so
every variant's imports run together:

```
stage 1 :  imports / updates   ‖   build-or-copy + annotate, across all tags × variants
              │ barrier
stage 2 :  aliases             ‖   copy from an out_tag (depends on stage 1)
              │ barrier
stage 3 :  deletes             ‖   target-level
```

- `skipped` operations are pure bookkeeping (no I/O) → computed outside the pool.
- The **stage 1 → stage 2 barrier is real**: an alias copies a `dest_repo:target` `out_tag` that may have
  just been imported in the same run.
- Each stage is a fan-out whose results are awaited before the next stage starts (the barrier *is* the
  `.result()` join). A `_run_stage(items, fn, *, executor)` helper either maps directly (sequential) or
  submits to the executor and joins.
- Each work-unit `fn` **catches its own exceptions** and returns a failed `Operation` (see failure model)
  rather than raising, so one failing tag never kills the stage.

Work-unit shapes:

- *stage 1* `(variant, out_tag, kind∈{imported,updated})` → `build_variant` or `registry.copy`, then
  `registry.annotate` → `Operation`.
- *stage 2* `(variant, alias_name, target)` → `registry.copy` → `Operation`.
- *stage 3* `(out_tag)` → `registry.delete_tag` → `Operation`.

After the stages, results are grouped back by variant (each `Operation` knows its variant) to rebuild the
existing `VariantReport` / `TargetReport` tree.

## Failure model — continue & collect

Each work unit returns a successful `Operation` **or** an `Operation` carrying an `ErrorInfo`
(built via `knock.errors.exit_code_for`, catching broad `Exception` exactly like the current
policy-level handler).

Model changes:

- `use_cases/report.py`
  - `Operation` gains `error: ErrorInfo | None = None` (set ⇒ the op failed; `applied=False`).
  - `PolicyStatus` **gains** `"partial"` (today it is only `ok | failed`). `VariantReport` and
    `TargetReport` **gain a new `status` field** of `Literal["ok", "partial", "failed"]`
    (partial = some tags failed, some succeeded). Run-level `RunStatus` already has `partial`.
  - `report_exit_code` must walk the **whole tree** and return the max exit code across every `ErrorInfo`
    (policy-level *and* operation-level), not just `policy.error`.
- `ports/reporter.py`
  - `Counts` gains `failed: int = 0`. A failed op increments `failed`, **not** its kind bucket — so
    `imported`/`updated`/… keep counting successes only. `_counts_of` / `_merge_counts` updated.

**What stays fail-fast (unchanged):**

- **Config errors** in the plan phase (unreadable cert, unknown mirror, alias collision) still raise
  *before any mutation*.
- A **login** failure fails the whole policy — we cannot proceed against that registry.
- Only per-tag **build/copy/annotate/delete** errors are collected.

## Reporter contract

- `ports/reporter.py`: docstring states `operation_applied` / `operation_failed` **may be called
  concurrently from multiple threads; implementations must be thread-safe**.
- New event `operation_failed(ev: OperationEvent, error: ErrorInfo)` — symmetric with `policy_failed`.
  `OperationEvent` is unchanged (`applied=False` for failures).
- `adapters/structlog_reporter.py`: a `threading.Lock` around emission. Events stream in real time,
  interleaved but attributable via `policy`/`variant`/`out_tag`.
- `cli/render.py`: render failed operations and `partial` status in the text output.

## Configuration & CLI

- `config.py`: `max_concurrency: int = 4` (env `KNOCK_MAX_CONCURRENCY`), validated `>= 1`. This is the
  only place the environment is read (house rule).
- `cli/reconcile.py`: `--concurrency` / `-j` option that **overrides** the config value when supplied,
  passed into `reconcile_policies(max_concurrency=...)`.
- `max_concurrency == 1` ⇒ sequential path (no executor), deterministic output.

## Thread-safety audit of the touched paths

- `tempfile.TemporaryDirectory(prefix="knock-build-", dir=work_dir)` → unique dir per build → **safe**.
  `work_dir.mkdir(parents=True, exist_ok=True)` under concurrency → `exist_ok=True` makes it safe.
- The `source: dict[str, SourceArtifact]` is **read-only** during apply → safe.
- CLI adapters are independent subprocesses. The **only** shared mutable state is the registry
  auth/hosts config file (regctl/skopeo), which is **written only** during the serial login barrier and
  **read only** during apply. Safe *as long as no login runs during the fan-out* — guaranteed by
  policies-sequential + login-before-apply.
- ⚠️ **The login-config file is per-process state.** Because policies are *not* parallelised in-process
  (they scale across pods, each its own process with its own home/filesystem), there is no cross-instance
  race on it — each pod logs in independently. This is precisely why horizontal scaling uses separate
  processes (sharding), not a shared in-process pool over policies.
- Reporter → guarded by its own lock (above).

## Determinism

The streamed events interleave, but the final `RunReport` must be **deterministic regardless of thread
completion order**. This is achieved by **preserving input (selection) order**, not by sorting:
`_run_stage` returns results in submission order (`[f.result() for f in futures]` joins in order), and the
report is assembled in that order — so the JSON stdout contract is stable and unchanged vs. the sequential
path.

## Testing strategy

Fakes journal calls (house convention). Add a `FakeImageBuilder` / `FakeRegistry` that can **block on a
latch** and **fail per tag**, to assert:

1. Parallelism actually happens — N work units observed in-flight concurrently (a latch/barrier in the
   fake proves overlap), and it respects `max_concurrency`.
2. Partial-failure collection — a failing tag yields a `partial` policy with the other tags applied.
3. `RunReport` is deterministic regardless of completion order (sorted operations).
4. `max_concurrency == 1` ⇒ strictly sequential (no overlap observed).
5. The reporter is called from multiple threads without corruption.

Strict TDD per house rule: failing test → red → minimal impl → green → commit, one behaviour per commit.

## Published artifacts to refresh

- **JSON Schema:** `report.py` changes alter `run_report_json_schema()` — regenerate/publish the committed
  schema if one exists (house rule: derive from Pydantic, never hand-write).

## C4 / examples impact

- **C4 (`docs/architecture/workspace.dsl`):** no change. This adds no actor, external system, or
  integration — it is an internal execution-model change, invisible at context/landscape level.
- **Examples (`docs/examples/`):** no new `MirrorPolicy` example. Concurrency is a runtime knob
  (`KNOCK_MAX_CONCURRENCY` / `--concurrency`), not policy schema. If a CLI-usage doc lists flags, add
  `--concurrency/-j` there.

## Relationship to horizontal scale-out

This in-process threading is the **scale-up** axis (parallel *tags* within one pod). The **scale-out**
axis (parallel *policies* across pods) is a separate design — see the
[horizontal sharding spec](2026-06-12-horizontal-sharding-design.md). They compose: a sharded pod owns a
subset of policies and threads the tags within each.

- **buildkitd coupling.** The *build* path (`build_and_push`) terminates at `buildkitd`, deployed
  `replicas: 1` today. In-pod build threading (and cross-pod sharding) only yields real build parallelism
  once buildkitd scales (replicas + Service + registry cache — detailed in the sharding spec). So
  `max_concurrency` is primarily a **copy-path** knob; the build-path ceiling is buildkitd capacity. Keep
  the default modest (4).
- **Idempotency.** `copy` (by digest), `annotate` (overwrite), and `alias` (overwrite) are idempotent, so a
  re-run or an overlapping run converges without corruption. Deletes are authoritative-per-repo and safe
  under single-owner sharding; the sharding spec carries the owning invariant.
