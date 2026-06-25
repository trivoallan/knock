# Scan pipeline — hardening the queue to supply-chain grade (Redis Streams, not Dapr)

> **Status:** Design (approved direction) — pre-implementation. Brainstorming pass 2026-06-25,
> follow-up to [2026-06-25-platform-scan-pipeline-orchestration-design.md](2026-06-25-platform-scan-pipeline-orchestration-design.md)
> (#187), which shipped the **topology** but left the queue mechanism as a hand-rolled reference
> implementation. This doc fixes the mechanism and adds the supply-chain-grade guarantees, **without
> adding net-new infra** — staying inside [ADR 0042](../../architecture/decisions/0042-platform-scan-pipeline-incremental-reconcile-fed.md)
> ("a bus/engine for one pipe is unjustified net-new infra"). **Zero new houba-core.**

## 1. Why this exists

#187 landed the right *shape*: `reconcile` emits `out_digest` → durable queue → KEDA-scaled worker
pool runs `regis scan` → `houba attach` → publish to Dependency-Track, with retry/DLQ. That shape is
**not** in question here and was deliberately built as a minimal "reference deployment".

The trigger for this doc: **this pipeline is becoming a load-bearing element of the org's software
supply chain.** That promotion changes the bar. A reference implementation is fine to demo; a
supply-chain-critical pipeline needs a base that is *auditable, observable, and free of hand-rolled
correctness traps*. The instinct was "rip it out, put Dapr underneath." We rejected that (§5) and
diagnosed the actual gap instead.

## 2. Diagnosis — the topology is correct; the *mechanism* is artisanal

Reading the shipped glue ([scripts/scan-queue-reserve.py](../../../scripts/scan-queue-reserve.py),
[scripts/scan-queue-reap.sh](../../../scripts/scan-queue-reap.sh),
[deploy/components/scan-pipeline](../../../deploy/components/scan-pipeline)):

- **Wrong primitive.** It uses the *old* Redis reliable-queue pattern: a `LIST` with
  `BRPOPLPUSH work → processing`, `LREM` to ack. This predates Redis's purpose-built primitive for
  exactly this job (Streams + consumer groups, Redis 5+/6.2+).
- **A fragile reaper.** Crash recovery is a two-snapshot stale-reaper CronJob whose own comment admits
  the trap: *"no per-item timestamps → staleness = the reaper INTERVAL → the CronJob schedule MUST
  exceed the max worker duration."* A slow scan (large image, many CVEs) that overruns the interval is
  **false-reaped and double-processed**. Idempotency saves correctness, but the staleness threshold is
  **global**, not per-item, and the coupling is a latent foot-gun as worker durations vary.
- **Hand-rolled wire protocol.** `scan-queue-reserve.py` speaks **RESP over a raw socket**
  (`_resp()`, parsing `$-1`/`*-1`) because there's no Redis client. Clever, but it's exactly the
  hand-rolled-correctness surface a critical pipeline should not carry.
- **Observability is logs, not metrics.** No queue depth / in-flight age / scan pass-fail / DLQ-size
  signals to alert or SLO on.
- **The out-of-band safety net was made optional.** ADR 0042 demoted the `houba audit --scan` coverage
  tier to "occasional insurance". For *critical* infra that is backwards (§4.4).

**Conclusion:** keep the topology, replace the *mechanism* with the Redis-native primitive, and spend
the freed budget on the guarantees that actually make a supply-chain pipeline trustworthy.

## 3. Decision — Redis Streams consumer groups + four hardening guarantees

Same Redis already in the deployment. Same KEDA. Same agnostic boundary (houba emits the list; fan-out
stays deployment glue). Same ADR 0042.

### 3.1 Queue mechanism: `LIST + reaper` → `Streams + consumer group`

| Concern | #187 (LIST) | This design (Streams) |
|---|---|---|
| Enqueue | `LPUSH work` | `XADD houba:scan:work * digest <d>` |
| Reserve | `BRPOPLPUSH work processing` | `XREADGROUP GROUP scan <consumer> COUNT 1 BLOCK …` |
| In-flight tracking | `processing` LIST | **Pending Entries List (PEL)** — built in |
| Ack | `LREM processing 1 <d>` | `XACK houba:scan:work scan <id>` |
| Crash recovery | two-snapshot reaper CronJob | `XAUTOCLAIM … MIN-IDLE-TIME <t>` — **per-item** timeout |
| Dead-letter | (none explicit) | route to `houba:scan:dead` when `delivery-count > N` |
| Scaling | KEDA `redis` LIST scaler | KEDA **`redis-streams`** scaler (**`streamLength`/XLEN** — see §11) |
| Client | raw-socket RESP | a real Redis client lib |

**What gets deleted:** the `processing` LIST, the entire reaper CronJob + its `seen` SET two-snapshot
dance, the interval-must-exceed-worker-duration coupling, and the raw-RESP parser. Crash recovery
becomes `XAUTOCLAIM` with a real per-item idle timeout (the visibility-timeout semantics you actually
wanted). `delivery-count` on each pending entry gives a principled DLQ threshold for free.

**The load-bearing invariant — `XACK` is always last.** Every durable side-effect of processing an
entry (the signed `houba attach`, the DT publish, the confirmed-set write of §3.4, the dead-letter
`XADD` of §3.3) completes *before* the `XACK`. Acking before a side-effect turns a crash into silent
loss — under-coverage. Concretely: `XACK` only after DT publish returns 2xx; on the dead-letter path,
`XADD houba:scan:dead` **then** `XACK` (a crash between them re-delivers and re-dead-letters — a
dedupable duplicate, never a loss).

**Trim by `XTRIM MINID`, never `MAXLEN` or per-entry `XDEL`.** `XACK` clears the PEL but the entry stays
in the stream, so the stream must be trimmed or it grows unbounded (Redis OOM). The right primitive is
`XTRIM houba:scan:work MINID <min-pending-id>` — `min-pending-id` from `XPENDING`; every entry below the
oldest un-acked one is fully processed and safe to reclaim. `MAXLEN ~ N` is **wrong** (a backlog —
regis is the throughput ceiling — can push past N and evict *un-acked* entries → silent loss);
per-entry `XDEL` is **wrong** (dangling PEL references under a consumer group). The reaper kept for
`XAUTOCLAIM` runs the `XTRIM MINID` in the same pass. **Requires Redis ≥ 6.2** (`XAUTOCLAIM` +
`XTRIM MINID`); #187 runs redis:7-alpine, so this holds.

### 3.2 Guarantee — idempotency keyed on digest

At-least-once delivery + an **idempotent worker** is the honest state of the art (exactly-once is a
myth). The worker is already idempotent (`houba attach` dedups the signed referrer, `gc` prunes). Make
it **explicit and tested**: the digest is the idempotency key; re-delivery of the same digest is a
verified no-op, not an accident that happens to be safe.

### 3.3 Guarantee — a DLQ a tired operator can triage *and replay*

`houba:scan:dead` is a stream, not a black hole. Wrap it in a thin **`scan-dlq`** tool (deployment glue,
not houba-core — a script in the worker image, runnable as a one-shot Job; raw Redis stays the escape
hatch) so the 3am-paged operator never hand-rolls `XRANGE`/`XADD`:
- `scan-dlq list` → table: digest, repo, failed-stage, error, delivery-count, dead-since
- `scan-dlq show <digest>` → full context **+ the suggested fix**
- `scan-dlq replay <digest | --all>` → re-enqueue to `work` (the safe default — after a transient
  registry outage, `--all` is one command); `scan-dlq drop <digest>` → permanent drop (image
  legitimately gone)

Each dead entry carries a **problem + cause + fix** payload, not a bare "last error":
`{digest, repo, stage (scan|attach|publish), error_class, error_excerpt, delivery_count, first_seen,
last_seen, suggested_action}`. `suggested_action` comes from the **same F5 classifier** that decides
dead-letter-vs-drop (§8) — e.g. `registry 5xx → transient, replay`; `manifest 404 → image gone, drop`;
`signer error → check HOUBA_ATTEST_SIGNER`. A poison image is then a triageable item *with a next step*,
not a silent loss in a supply-chain pipeline.

### 3.4 Guarantee — observability as metrics + an out-of-band coverage proof

Two distinct needs, do not conflate them:

- **Pipeline health (metrics/SLO):** export queue depth, oldest-pending age, `XPENDING` count, DLQ
  size, scan pass/fail, per-stage latency. KEDA already reads the stream; surface the same numbers to
  Prometheus so you can alert and set SLOs.
- **Coverage proof (the real supply-chain anchor):** an **independent** convergence check that does not
  trust the queue. Compute **placed-digests − fresh-confirmed-digests** — both sets cheap and
  houba-side, **no DT query, no registry walk:**
  - `placed` = a houba-side **SET `houba:scan:placed`** the enqueuer maintains: it already sees every
    placed digest (it `XADD`s them), so it also `SADD`s each one. (Originally specced as "reconcile's
    enumeration", but reconcile's report carries only the *applied* `out_digest` delta — `None` unless
    applied, and **empty under `--dry-run`** — so deriving `placed` from it yields a false-green. The
    enqueuer SET is the correct full-placed source, still zero houba-core. Pruning deleted images from
    the SET is a later refinement: over-reporting a gap is the safe direction, never a false-green.)
  - `fresh-confirmed` = a houba-side **ZSET `houba:scan:confirmed`** scored by the signed `attested_at`;
    the worker `ZADD`s the digest on a successful DT publish. Fresh coverage =
    `placed − ZRANGEBYSCORE(now − max_age, now)`. **One ZSET serves both** the coverage set-diff *and*
    the freshness-age metric (D3) — no second source of truth. ~150k entries ≈ 20–30 MB; the diff is a
    few ms.

  The gap is "images the pipe silently dropped" — and the check emits **the gap list, not just a
  count**: each uncovered digest joined with the stamp's `owners` (already a comma-joined Backstage
  entity-ref on every placed image), so a security lead reads *"12 uncovered, owned by team-X (5),
  team-Y (7)"*, not an anonymous `N` (a number without the drill-down is anxiety, not information). Same
  owner-join the CVE blast-radius already does (#156), applied to coverage gaps. It stays
  **producer-side** (a structured metric label + the list surfaced in `scan-dlq` / runbook output),
  **not** the coverage portal (Later) — the portal would *consume* this, houba just emits it
  actionably. DT stays the *consumption* surface (blast-radius queries), never the coverage-check
  source — "houba produces, DT consumes" stays clean. A full `audit --scan` registry walk
  (46–115 h over 150k, ADR 0042) remains the *optional* insurance for the separate "bypassed the front
  door" question, not the routine check.

This convergence loop is the SOTA move for critical infra: **don't trust the tuyau, verify coverage
out of band.** It is a second reconcile loop, symmetric with houba's whole design ethos.

## 4. Scope & non-goals

- **Zero new houba-core.** Everything above is `deploy/` + `scripts/` glue over reconcile's existing
  `out_digest` output and the existing `houba attach` / DT publish. The coverage check reuses data
  houba already emits; it adds no per-image registry probe.
- **KEDA stays.** Streams does not scale workers; the `redis-streams` scaler replaces the `redis`
  (LIST) scaler. One-line trigger change.
- **No workflow engine.** ADR 0042 holds: the flow is linear (scan → attach → publish), the SBOM is
  produced at placement independent of scan — there is no DAG to orchestrate.
- **Out of scope:** the bypass question (images that never went through the front door) — still the
  optional `audit --scan` walk, unchanged. Lifting the per-image probe ceiling (a persistent registry
  client) remains explicitly out, against "no HTTP layer".

## 5. Alternatives considered

**B — Broker substrate (NATS JetStream / Kafka / SQS).** Native durable consumers, ack/redelivery,
DLQ; KEDA scalers exist. *Rejected for now:* it is **net-new infra to operate** for a single consumer,
which is precisely what ADR 0042 ruled out. Revisit if the worklist genuinely grows multiple
independent consumers or needs streaming retention — then JetStream (lightest) is the first candidate,
and §3's guarantees port over unchanged.

**C — Dapr (pub/sub + resiliency policies).** Would replace the queue glue with a managed building
block. *Rejected:* (1) the requester is not committed to Dapr — it was shorthand for "something solid";
(2) it adds a sidecar-per-pod + control plane (placement, sentry, operator, mTLS) **into the trusted
computing base of the most security-sensitive pipeline in the org** — criticality argues for a *smaller*
TCB, not a larger one; (3) it runs against houba's "no HTTP layer" grain (Dapr is a localhost-HTTP/gRPC
sidecar); (4) ADR 0042's net-new-infra-for-one-pipe rejection applies *a fortiori*. Reopen **only** if
Dapr becomes the platform-wide standard — then this is an org platform decision, not a pipeline one,
and the queue (being deployment glue) can adopt it without touching houba-core.

**Why A wins:** the evidence says the topology is already right and only the mechanism is hand-rolled.
Redis Streams deletes exactly the fragile code (reaper coupling, raw RESP) with **no new infra**, stays
faithful to an ADR merged the same week, and frees the budget for the guarantees in §3.2–3.4 — which
are what actually make a supply-chain pipeline "state of the art", and are independent of queue tech.

## 6. Risks & open questions

- **Redis durability is the floor.** Streams persist with the rest of Redis — confirm AOF
  (`appendonly yes`, `appendfsync everysec`) on the scan-queue Redis so an enqueued worklist survives a
  pod restart. (Same exposure #187 already had; make it explicit.)
- **DLQ threshold N.** Pick `delivery-count` ceiling against observed transient-failure rates
  (registry 5xx, regis flakes) so you don't dead-letter a recoverable scan; start conservative (e.g. 5)
  and tune from metrics.
- **Coverage-check source — RESOLVED (eng review, §3.4).** Not a DT query: a houba-side ZSET
  `houba:scan:confirmed` (digest → `attested_at`) written by the worker on publish, diffed against
  reconcile's placed-set. Caveat (P3): a Redis wipe drops the ZSET → everything reads as a gap →
  re-scan herd; AOF survives restarts, and a cold-start rebuild of the confirmed-set from DT is the
  filet.
- **`XAUTOCLAIM` min-idle-time vs. longest legitimate scan.** "Idle" = time since delivery, and the
  worker does **not** touch Redis during a scan (regis is a subprocess) — so a long scan *looks* idle.
  Set `min-idle-time = 2 × the p99.9 scan duration` measured in the §7 spike, **plus an alert when any
  scan exceeds min-idle** so a broken assumption is caught, not suffered. Per-item and decoupled from a
  CronJob, so the failure mode is far softer than #187's.

## 7. The assignment (next concrete step, not "go build it")

Before any implementation: **run a 30-minute spike that proves the Streams crash-recovery semantics on
your real worker durations.** Stand up the scan-queue Redis, `XADD` ~20 digests, start a worker that
`XREADGROUP`s and deliberately dies mid-scan, and confirm `XAUTOCLAIM MIN-IDLE-TIME` re-delivers
exactly the dropped entry with an incremented `delivery-count` — and that a long-but-alive scan is
**not** claimed. Measure the p99.9 scan on a **big real image** (many CVEs), not a toy — that number
sizes `min-idle-time` (= 2×, §6). That single experiment retires the one real risk (the
visibility-timeout tuning) and turns this design into an executable plan. If it holds, the rest is a mechanical glue swap with
guarantees attached.

**Spike result — DONE (2026-06-25, real Redis 7.0.15).** All checks passed:
`XAUTOCLAIM(min-idle)` did **not** reclaim an entry idle < min-idle (alive worker safe), **did** reclaim
a dropped entry once idle > min-idle with `delivery_count → 2` (recovery works), and — the load-bearing
finding — the claim is **purely idle-based**, so a long-but-alive scan past min-idle is stolen and
double-scanned. That confirms the sizing rule: `min-idle = 2 × p99.9 scan + alert on exceed` (§6). The
trim anchor also held: `XTRIM MINID` reclaimed the acked entry and **kept** the un-acked one, while
`MAXLEN` **evicted** an un-acked entry (the data-loss footgun the design rejects, §3.1). The one real
risk is retired; this is now a mechanical glue swap. (Spike script: `/tmp/spike_xautoclaim.py` — the
seed for the T4 integration test against `redis:7-alpine` in CI.)

## 8. Review outcomes (CEO review, 2026-06-25, HOLD SCOPE)

A `/plan-ceo-review` pass over this design (HOLD SCOPE — the scope is right, make it bulletproof)
settled three decisions and promoted three silent-failure fixes into scope. The framing that drove all
of them: for load-bearing supply-chain infra the catastrophic failure is **silent under-coverage** (a
placed image that is never scanned makes a blast-radius query answer "clean" on an image nobody looked
at), so every gap below is a variant of Prime Directive #1, *zero silent failures*.

### Decisions

- **D1 — sequence the swap before this goes load-bearing.** The #187 queue runs as a *reference
  deployment* (e2e on kind), not yet on the real ~150k Harbor. While it is not load-bearing, LIST→Streams
  is a two-way door (replace the component, no in-flight entries to migrate). Once it is, it becomes an
  in-flight queue migration (drain / dual-run). **Do the hardening now**, before the prod cutover — no
  migration window.
- **D2 — Redis stays single, but the SPOF is made *detected*, not eliminated.** AOF
  (`appendonly yes`, `appendfsync everysec`) + alerts (queue-not-draining, `enqueue_failed`) + the
  coverage set-diff as the backstop. Redis HA (Sentinel/replica) is **YAGNI** for one pipe until scale
  demands it (an HA cluster for a single consumer frets against ADR 0042). The bet: a SPOF you *see* is
  acceptable; a SPOF that fails silently is not.
- **D3 — the rescan-freshness loop is in scope, minimal.** A signed scan from months ago passes the
  admission max-age gate (ADR 0033, enforced admission-side). What keeps it fresh is the rescan:
  DT flags a new CVE → re-enqueue the blast-radius into the same stream. Wire **the re-enqueue + a
  freshness-age metric**, no scheduler/SLA-tier subsystem (that would be over-engineering). Coverage
  must be true *over time*, not just at t0.

### Promoted to scope (silent-failure fixes, not optional)

- **P1 — trim the stream (F1).** `XACK` clears the PEL but the entry stays in the stream; at 150k +
  rescans it grows unbounded → Redis OOM → the SPOF realizes itself. Trim with
  `XTRIM MINID <min-pending>` (§3.1) — **not** `MAXLEN` (evicts un-acked under backlog) or per-entry
  `XDEL` (dangling PEL refs) — plus a retention policy on the dead stream. (#187's `LIST` did not have
  this trap — `LREM` reclaimed; Streams does not.)
- **P1 — `enqueue_failed_total` metric (F1-bis).** The enqueuer is best-effort so it never blocks
  reconcile — correct, but a failed `XADD` during a placement is silent under-coverage. The coverage
  set-diff is the backstop; a counter makes the failure *visible at the source*, not only on the next
  convergence sweep.
- **P2 — transient vs permanent scan failure (F5).** An image deleted between placement and scan fails
  *permanently*; treating it as transient burns N redeliveries then pollutes the dead stream. Detect
  "image gone" (regis exit / `regctl` probe) → clean drop, not dead-letter.

### Observability spec (the real gap — first-class, in scope)

- **Metrics:** stream length, PEL size (in-flight), oldest-pending age, dead-stream size,
  delivery-count distribution, scan pass/fail, `enqueue_failed_total`, coverage-gap count (+ a
  **by-owner** label, §3.4), scan freshness-age.
- **Alerts:** dead-stream growing, coverage-gap > threshold, `enqueue_failed` > 0, oldest-pending age >
  freshness SLA, PEL stuck (queue not draining).
- **Runbooks (decision tree → act → *verify recovery*, not a one-liner):** e.g. "queue not draining" →
  Redis reachable? (no → SPOF restart/failover, AOF survived) → workers up? (no → KEDA / scaler / image
  pull) → regis healthy? (no → scan capacity) → one digest looping? (`scan-dlq show <digest>` → drop or
  replay); **verify:** PEL size + oldest-pending age falling. Same shape for "dead stream growing" and
  "coverage gap" (→ `scan-dlq` / the by-owner gap list). The verify step is what operators always lack:
  "how do I know it's fixed."

### Out of scope (explicitly deferred)

- **Developer coverage portal** — the consumption surface stays in roadmap *Later* (graduate only on a
  real demand signal). This pipeline is the **producer**; it must not grow into the query engine.
- **Audit-side freshness enforcement** — rejected by ADR 0033 (an audit tier reports drift but cannot
  block a deploy). The coverage set-diff here is *observability + safety net*, never an enforcement
  point; admission enforces max-age against the signed `attested_at`.
- **Redis HA** (per D2) and a **full rescan subsystem** (per D3).

## 9. Review outcomes (eng review, 2026-06-25)

A `/plan-eng-review` pass over §3 confirmed the design is executable with **no re-design**, and produced
three execution-level refinements (now folded into §3.1, §3.4, §6) governed by one rule — the `XACK`-is-
last invariant (§3.1). The two places where a mistake means *silent under-coverage* are the **trim**
(§3.1 — `XTRIM MINID`, never MAXLEN/XDEL) and the **crash-recovery window** (§6/§7 — `min-idle` vs. scan
duration); both must carry tests before this goes load-bearing.

### Test strategy

The glue is `deploy/` (not houba-core, so the ≥90 % domain gate does not apply; e2e-on-kind is the #187
convention) — but mirror houba's own ports/adapters split *inside* the glue: pull the **decision logic**
out of the Redis I/O into a small pure module so most of it is unit-tested without a broker.

```
UNIT (pure, no Redis):
  • out_digest → XADD args   (gotcha: ref = dest_repo@out_digest; do NOT re-prefix the host)
  • coverage set-diff        (placed − fresh-confirmed; empty-set cases)
  • dead-letter decision     (delivery-count > N)
  • transient-vs-permanent classification (F5 — "image gone")
INTEGRATION (redis:7-alpine container in CI, no kube):
  • reserve / ack / XAUTOCLAIM / XTRIM-MINID / dead-letter ordering
  • "trim never reclaims an un-acked entry"  ← the anti-data-loss anchor
  • crash-recovery (the §7 spike, promoted to a test): kill a worker mid-scan → re-delivered +
    delivery-count++, and a long-but-alive scan is NOT claimed
    (inject a tiny min-idle + deterministic sleeps — never wall-clock timing, or the test is flaky)
E2E (kind, few, slow):
  • reconcile → enqueuer → worker → attach → DT (forced churn — the #187 convention)
  • chaos: kill Redis mid-run → workers fail loud (no XACK), entries survive (AOF), recover on restart
```

The two "ship-at-2am-Friday" anchors: the trim-MINID test (proves no loss) and the crash-recovery test
(proves no silent drop). The hostile-QA test: a digest whose image is deleted mid-flight → dead-letters
cleanly (F5), does not wedge the queue.

## 10. Operator experience (devex review, 2026-06-25)

This pipeline is internal infra, not a developer product — but it has a real **operator** surface (the
platform/security engineer who gets paged). A focused devex pass (`/plan-devex-review`) against that
persona raised the operator experience from raw-Redis spelunking to a *pit of success*; the retained
decisions are folded into §3.3, §3.4, §8 above.

```
OPERATOR PERSONA — paged at 3am, half awake
  Wants:   diagnose + act in minutes, from a laptop; a command that says what's wrong and what to do
  Refuses: hand-rolling XRANGE/XADD against a production supply-chain queue
```

| # | Finding | Before → after | Folded into |
|---|---|---|---|
| 1 | DLQ was "XRANGE / XADD by hand" | 3 → 8 — `scan-dlq list/show/replay/drop`, raw Redis as escape hatch | §3.3 |
| 2 | Dead entry was a bare "last error" | 4 → 9 — problem+cause+fix payload + `suggested_action` (reuses the F5 classifier) | §3.3 |
| 3 | Runbooks were one-liners | 5 → 9 — decision tree → act → **verify recovery** | §8 |
| 4 | No operator onboarding | 0 → 7 — a "running the scan pipeline" how-to; TTHW-equiv = time from `kustomize apply` to first green scan | task (P2, docs/how-to) |
| 5 | Coverage was an anonymous count `N` | 4 → 8 — emit the gap **list joined with `owners`**, producer-side (not the portal) | §3.4 |

Overall operator DX ~3/10 (Redis spelunking) → ~8/10 (pit of success). Principles applied: *every
error = problem + cause + fix* (2), *pit of success / decide-for-me-let-me-override* (1), *systems over
heroes — design for the tired 3am human* (3), *fight uncertainty* (5). Finding 4 is the only one not
folded as design — it is a doc deliverable (P2), tracked as a task.

## 11. e2e outcomes (kind, 2026-06-25)

Run against the live `houba-demo` kind cluster (KEDA 2.20.1, in-cluster Redis 7.4.9). The full
deploy-via-ArgoCD e2e is gated on merging the branch (the demo syncs from git); what was validated
directly:

- **Scripts vs. the real cluster Redis (7.4.9).** `scan-enqueue.py` and `scan-coverage.py` run correctly
  against the in-cluster `scan-queue-redis` (port-forwarded, probe keys): enqueue `XADD`s + `SADD`s the
  placed-set; coverage returns the right gap. Confirms the Redis version meets the ≥6.2 floor
  (XAUTOCLAIM / XTRIM MINID) and that the real entrypoints work, not just the test module.
- **KEDA scaler bug caught + fixed (§3.1).** A probe `ScaledJob` proved `pendingEntriesCount` (the
  original config) **never scales a worker for fresh work**: `XPENDING` is 0 for an un-read entry, so the
  metric is always 0 → cold-start deadlock (the pipeline would process nothing). The same probe with
  **`streamLength`** fired immediately. The scaler is now `streamLength`. `kustomize build` could not
  have caught this — only the e2e did.

Still e2e-pending (on merge / a full deploy): the worker reserve→scan→attach→ack ordering across
containers, AOF surviving a pod restart, and the dead-letter→`scan-dlq` triage path.

---

*Implementation-time follow-ups (not part of this design doc): mirror as a thin ADR under
`docs/architecture/decisions/`, and refresh `workspace.dsl` (the queue component the #187 spec deferred
is now concrete: Redis Streams + dead-letter stream + coverage-reconcile CronJob).*
