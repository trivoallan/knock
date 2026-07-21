# `knock purge` — the reference reaper (usage-gated purge of marked tags)

**Status:** Draft — pending review
**Date:** 2026-06-13
**Related:** [`2026-06-12-delegated-tag-deletion-design.md`](2026-06-12-delegated-tag-deletion-design.md) (produces the `pending-deletion` referrer this command consumes — **must land first**); [`2026-06-11-reconcile-output-design.md`](2026-06-11-reconcile-output-design.md) (the partial-failure/run-summary model reused here); [`2026-06-12-concurrent-reconcile-design.md`](2026-06-12-concurrent-reconcile-design.md) + [`2026-06-12-horizontal-sharding-design.md`](2026-06-12-horizontal-sharding-design.md) (the scale-up/scale-out primitives the catalog walk reuses); roadmap item ⑤ *Lifecycle — `archive_purge`/`archive_restore`*.

> Written in English to match the rest of `docs/` and the public-repo convention. Field and command names are the public API.

---

## 1. Problem

The delegated-tag-deletion design (#41) lets knock **mark** an undesired tag with a `pending-deletion`
OCI referrer instead of hard-deleting it, then explicitly **delegates the verify-and-purge decision
to an external reaper** — because *"knock has no visibility into what is deployed"*. Its non-goals
state plainly: **"No reaper implementation … the reaper is an external system"** and **"knock never
executes a delegated purge."**

That leaves a real, named gap: **someone has to be the reaper.** Without one, marked tags accumulate
forever and the soft-delete path delivers no lifecycle value. The reaper's job is narrow and
well-defined: discover the marks, ask the authority that *can* answer "is this still used in prod?",
and purge only what is safely unused.

This design fills that gap by shipping the reaper **as a knock subcommand**, `knock purge`, while
keeping it cleanly separable.

## 2. Goal & positioning

Ship `knock purge`: a **reference reaper** that

1. discovers `pending-deletion` marks by scanning the registry's referrers (stateless, no policy
   files),
2. for each candidate asks a generic **usage oracle** (e.g. Datadog) whether the image's content was
   seen in production within a recency window, and
3. purges only the candidates that are **not** in recent prod use, leaving the rest marked for the
   next run.

### 2.1 Reconciling with the product thesis (resolves the #41 non-goal)

The roadmap fences off *"runtime presence / fleet inventory"* — **knock must not watch where its
images run.** A purge command that queries observability appears to cross that line. It does not, and
the distinction is load-bearing:

- **Forbidden:** knock *owning/maintaining* runtime state — a fleet inventory, a watcher, an operator.
- **This command:** a **stateless, point-in-time question** to the observability stack the thesis
  already designates as the source of truth ("blast-radius = one query in observability"), acted on
  immediately and forgotten. knock stores nothing, watches nothing.

Asking ≠ watching. `knock purge` is the *logical endpoint* of the thesis (consume the observability
stack), not a violation of it. We therefore **revise #41's "the reaper is an external system"
non-goal honestly**: knock ships *a reference reaper*. To keep the thesis intact in both code and
story, the reaper is held to **discipline B**:

- It lives **behind its own ports** (`UsageOraclePort`) and its own use case (`use_cases/purge.py`).
- It **shares none of reconcile's orchestration** nor the build/transform/copy path; it reuses only
  `RegistryPort` (the same registry primitives, including its delete methods), through its own use
  case.
- It is documented as **replaceable**: the org may swap `knock purge` for their own reaper; the
  contract it relies on is purely #41's referrer + artifactType. The extraction seam to a separate
  sibling tool (à la `regis`) is kept clean.

## 3. Command surface

```
knock purge [--registry <name>] [--apply]
```

- **Stateless, registry-wide.** No policy directory argument. Candidates are discovered by scanning
  referrers (§4), so a deleted policy's orphaned marks are still reaped.
- **Dry-run by default.** Without `--apply`, compute and print the plan (per candidate: `purge` /
  `protect` / `uncertain`, with the oracle's reason) and **mutate nothing**. `--apply` performs the
  deletions. The plan is also suppressed-from-mutation when `KNOCK_DRY_RUN_DELETIONS=true` — for a
  destructive operation the two gates are deliberately belt-and-suspenders; `--apply` is the explicit
  per-invocation gate, the env var the deployment-wide one.
- `--registry <name>` bounds the walk to one registry from the roster; absent ⇒ every registry in
  `KNOCK_REGISTRIES`.
- **Exit codes** via the existing `exit_code_for` hierarchy: `0` success (incl. a clean dry-run);
  non-zero if any candidate failed (partial-failure model, §7), so a scheduler sees red.

## 4. Data flow

```
for each target registry (roster, optionally --registry):
  list_repositories(registry)                         # NEW port method (§6)
    for each repo: list_tags(repo)
      for each tag: list_referrers(tag, PENDING_TYPE) # from #41
        for each pending mark:
          candidate = parse_pending_mark(referrer)     # pure (§5)
          digest    = inspect(repo:tag).digest         # the content under judgment
          since     = now − minIdle                    # pure (§5), clock injected
          obs       = oracle.last_prod_usage(UsageQuery{digest, ref, identity, since})
          decision  = decide_purge(obs)                # pure (§5)
            PROTECT   (obs.last_seen ≠ None)  → leave the mark; re-evaluated next run
            PURGE     (obs.last_seen = None)  → delete_tag + delete_referrer   [only if --apply]
            UNCERTAIN (oracle errored)        → fail-closed = PROTECT, reported
```

`PENDING_TYPE = application/vnd.knock.lifecycle.pending+json` (the artifactType #41 attaches).

**Steady-state convergence (no persistent state).** A protected or uncertain candidate keeps its
mark; once its prod usage ages past `minIdle`, a later run purges it. The system converges with
nothing stored between runs.

**The catalog walk is the only scaling concern** — it is O(repos × tags) referrer queries. It
**reuses the existing scale-up (concurrency) and scale-out (sharding) primitives** built for
reconcile (#37): the walk fans out concurrently and shards horizontally exactly as reconcile does,
and `--registry`/`KNOCK_REGISTRIES` already bound it. No new scaling mechanism is introduced.

### 4.1 Why key on digest (not tag), and the one honest caveat

The oracle is asked about the **manifest digest** the marked tag currently resolves to, not the tag
string. This is the **more conservative** choice: "if this *content* is running in prod, do not touch
its tag," independent of whether consumers pull by tag or by digest. The mark's subject already binds
a digest, so the reaper has it in hand (one `inspect` to get the current value).

Honest caveat, documented not fixed: on the **copy path** (no transform), the knock digest equals the
upstream digest, so a container that pulled the *same content directly from the upstream* (not from
knock's mirror) would also match. That is a **false-positive toward safety** — purge protects a tag
it might not have needed to — which is acceptable for a destructive operation. The oracle query
carries `image_ref` and the provenance `identity` as well, so a future adapter may tighten the match
(e.g. require the running image's registry to be knock's) without a contract change.

## 5. Domain — `knock/domain/purge.py` (pure, ≥ 90 % coverage)

No I/O, no mode/credential knowledge. Three small pure surfaces:

```python
@dataclass(frozen=True)
class MarkIdentity:                       # the 3-level stamp identity #41 writes into the mark;
    policy: str                          # introduced here (no such type exists today — stamp.py
    import_: str                         # only emits io.knock.policy/import/variant annotations).
    variant: str                         # shared by MarkedCandidate and UsageQuery.

@dataclass(frozen=True)
class MarkedCandidate:
    image_ref: str                       # registry/repo:tag carrying the mark
    identity: MarkIdentity               # policy / import / variant (from the mark payload)
    marked_at: datetime                  # audit/report only — NOT a decision input
    reason: str                          # carried through to the report

class PurgeDecision(StrEnum):
    purge = "purge"
    protect = "protect"
    uncertain = "uncertain"

def parse_pending_mark(annotations: dict[str, str]) -> MarkedCandidate: ...
    # exact inverse of #41's build_pending_deletion_annotations — defined against the same keys
    # so the read- and write-sides cannot drift.

def usage_window_start(now: datetime, min_idle: timedelta) -> datetime:
    return now - min_idle

def decide_purge(observation: UsageObservation | None) -> PurgeDecision:
    if observation is None:                 # oracle errored / timed out
        return PurgeDecision.uncertain      # → fail-closed PROTECT in the use case
    if observation.last_seen is not None:   # seen in prod within [since, now]
        return PurgeDecision.protect
    return PurgeDecision.purge              # not seen in the window ⇒ safe to purge
```

- `marked_at` is intentionally **not** a decision input: the prod-usage window is the sufficient
  guard (#41 — "the reaper owns timing"). It is reported for audit.
- The threshold lives **only** in the domain (`usage_window_start`) — knock owns *"how many idle days
  is safe"*; the oracle script owns *"what counts as prod"* (§7.1). Clean split.

## 6. Ports & adapters

### 6.1 New port — `knock/ports/usage_oracle.py`

```python
@dataclass(frozen=True)
class UsageQuery:
    digest: str                  # primary key — sha256:… the marked tag resolves to
    image_ref: str               # corroborating; lets richer adapters match by ref
    identity: MarkIdentity       # policy/import/variant; for adapters that query the stamp
    since: datetime              # look-back lower bound = now − minIdle

@dataclass(frozen=True)
class UsageObservation:
    last_seen: datetime | None   # most recent prod sighting in [since, now]; None ⇒ none
    detail: str                  # human reason for the report ("cluster prod-eu, 3d ago")

class UsageOraclePort(Protocol):
    def last_prod_usage(self, query: UsageQuery) -> UsageObservation: ...
```

### 6.2 New adapter — `knock/adapters/command_usage.py`

`CommandUsageAdapter` drives a **configured subprocess** — the exact idiom of the regctl/buildctl
adapters, and the reason knock needs no HTTP layer for observability. Observability backends become
*configuration of a generic primitive*; "Datadog" is one script.

- **Invocation:** runs `KNOCK_USAGE_ORACLE_CMD` with a single **JSON object on stdin**:
  `{"digest","image_ref","identity":{"policy","import","variant"},"since":"<ISO-8601>"}`.
  (JSON-on-stdin, not argv — extensible, no quoting hazards.)
- **Result:** the command prints **JSON on stdout**: `{"last_seen":"<ISO-8601>"}` or
  `{"last_seen":null}`.
- **Failure semantics:** exit `0` = answered; non-zero, timeout (`KNOCK_USAGE_ORACLE_TIMEOUT`), or
  unparseable stdout ⇒ raise `UsageOracleError`. No retry (adapter rule).
- **Datadog is shipped as an example script** (§9), not as in-tree code.

### 6.3 `RegistryPort` additions

- **NEW: `list_repositories(registry: str) -> list[str]`** — the catalog-walk root. Neither present
  today nor added by #41 (which only added *per-tag* referrer methods). `RegctlAdapter` implements it
  over `regctl repo ls <registry>`. Caveat to document: some registries gate `_catalog` (Harbor may
  require suitable credentials and paginates); the walk handles pagination and surfaces an
  access/enumeration failure as `RegctlError` rather than silently reaping a partial set.
- **Consumed from #41:** `list_referrers(image_ref, artifact_type)`, `delete_referrer(referrer_ref)`,
  and the `Referrer` model. Plus the pre-existing `inspect` (digest resolution) and `delete_tag`.

### 6.4 Reporter & errors

- `OperationKind` (`knock/ports/reporter.py`) gains **`purged`** and **`protected`**. `uncertain` is
  reported as `protected` with a distinguishing `reason` (it *is* a protect), keeping the event
  surface small. `Counts` gains `purged` / `protected` fields for the run summary.
- `knock/errors.py` gains **`UsageOracleError(AdapterError)`** → exit code **2** via the unchanged
  `exit_code_for` MRO walk.

## 7. Use case — `knock/use_cases/purge.py`

Orchestrates the §4 flow and applies the mode/safety policy the pure domain stays out of:

- **Fail-closed everywhere.** `uncertain` ⇒ protect. A per-candidate `UsageOracleError` ⇒ that
  candidate is protected and recorded (continue-on-error), never purged on doubt.
- **Oracle is mandatory.** If `KNOCK_USAGE_ORACLE_CMD` is unset, purge **refuses to run** with a
  `ConfigError` (exit 3) — you cannot verify, so you cannot purge. It never falls back to
  purge-everything.
- **`minIdle` has no default.** `KNOCK_PURGE_MIN_IDLE_DAYS` unset ⇒ `ConfigError`. The example's "15
  days" is the operator's value, never a knock default (a destructive default window is unsafe).
- **Global threshold, by construction.** Because purge is policy-decoupled (§3, it loads no
  policies), there is no policy/destination cascade for `minIdle`; it is a single global knob. A
  future per-product nuance would be encoded into the *mark payload* at `mark` time, not re-derived
  here.
- **Purge = `delete_tag` + `delete_referrer`.** Deleting the tag alone can leave an orphan mark when
  the digest survives under another tag; clearing the referrer keeps the operation tidy and
  idempotent (a re-run finds nothing).
- **Partial failure** mirrors reconcile: per-candidate status is collected; one failure (oracle,
  delete, a tag that vanished between scan and `inspect`) does not block the others; exit non-zero if
  any failed.

### 7.1 Separation of concerns (why the oracle is generic)

| Question | Owner |
|---|---|
| *"How many idle days is safe to purge?"* | knock domain + `KNOCK_PURGE_MIN_IDLE_DAYS` |
| *"What counts as production usage?"* | the oracle **script** (its prod filter, e.g. `env:prod`) |
| *"Was this digest seen in prod since `since`?"* | the oracle **backend** (Datadog, …) |

knock never encodes "prod". The script does. This is the CLAUDE.md rule ("org-specific … becomes
configuration of generic primitives") applied to observability.

## 8. Config — `knock/config.py`

New `KNOCK_*` settings (the only place env is read; JSON-in-a-var convention preserved):

- `KNOCK_USAGE_ORACLE_CMD: str | None = None` — the oracle command (required for purge; absent ⇒
  `ConfigError`).
- `KNOCK_USAGE_ORACLE_TIMEOUT: int` — per-call timeout seconds (sane default, e.g. 30).
- `KNOCK_PURGE_MIN_IDLE_DAYS: int | None = None` — the recency window; required for purge.

`reconcile` is unaffected by all three (untouched deployments unchanged). The policy schema does
**not** change — the threshold is global, not a policy field — so no policy JSON-Schema churn; the
**config** JSON Schema is regenerated from the models per "derive, never hand-write".

## 9. Architecture sync (required by CLAUDE.md)

- **C4.** #41 introduced an *external reaper*; this design makes **knock itself the reference
  reaper** and introduces a **new external system — the usage oracle / observability stack —
  *queried by* knock**. `docs/architecture/workspace.dsl` is updated in the same change: the new
  external system, a `knock → oracle` "queries prod usage" relationship, and (Container/Component
  views) the `UsageOraclePort` + `CommandUsageAdapter` + `purge` use case + the new
  `RegistryPort.list_repositories`. The #41 "external reaper" actor is reconciled to knock's `purge`
  command. Mirrored as a thin ADR **`docs/architecture/decisions/0013-purge-reaper.md`** linking
  here.
- **Examples.** Add a `docs/examples/` walkthrough: a tag is marked (#41) → `knock purge` (dry-run)
  reports it `protect` while in prod use → after the idle window it reports `purge` → `--apply`
  removes tag + mark. Ship the **example oracle script** `docs/examples/oracles/datadog.sh`
  (stdin-JSON → Datadog API filtered `env:prod` on `container.image_id == digest` → stdout
  `{"last_seen":…}`), explicitly marked as a replaceable reference.

## 10. Testing & verification (strict TDD)

- **Domain unit tests** (`tests/unit/domain/`): `decide_purge` — last_seen present ⇒ protect;
  None ⇒ purge; observation None ⇒ uncertain. `usage_window_start` arithmetic. `parse_pending_mark`
  round-trips #41's `build_pending_deletion_annotations` (shared keys, empty-prefix collapse,
  3-level identity, marked-at parsing).
- **Use-case tests** (`tests/unit/use_cases/`): with `FakeUsageOraclePort` (seed `last_seen` per
  digest, journal calls) and the existing `FakeRegistryPort` (seed referrers, journal
  `.deleted`/`.deleted_referrers`): purge deletes only candidates with no recent prod usage; protects
  the rest and **leaves their marks**; `uncertain`/oracle-error candidates are protected, never
  deleted; dry-run (no `--apply`) mutates nothing; `--apply` deletes; unset `KNOCK_USAGE_ORACLE_CMD`
  or unset `KNOCK_PURGE_MIN_IDLE_DAYS` ⇒ `ConfigError`; partial failure exits non-zero without
  blocking siblings.
- **Integration** (`tests/integration/`): a **fake-bin oracle** (branch on `FAKE_ORACLE_SCENARIO`,
  echo a `last_seen` JSON, append stdin to `FAKE_ORACLE_LOG`) asserts `CommandUsageAdapter` sends the
  exact stdin JSON and maps stdout/exit/timeout correctly; extend the `regctl` fake-bin with
  `repo ls` + the #41 referrer scenarios and assert `RegctlAdapter` emits the exact commands for the
  walk and for `delete_tag` + `delete_referrer`.
- Coverage gates unchanged: ≥ 80 % global, ≥ 90 % `knock.domain`. `cli/_di.py` excluded.

## 11. Non-goals

- **No fleet inventory, no watcher, no operator.** purge stores nothing between runs and never
  subscribes to runtime events — it asks a point-in-time question and forgets (§2.1).
- **No in-tree Datadog (or any backend) client.** The oracle is a generic command; backends are
  scripts. No HTTP dependency enters knock.
- **No per-policy purge scope or threshold cascade.** purge is registry-wide and policy-decoupled;
  `minIdle` is global (§7).
- **No change to the `mark`/`unmark` path.** That is #41's; purge only consumes its output.
- **`marked-at`-based timing / TTL.** The prod-usage window is the only guard.

## 12. Risks

- **Hard dependency on #41.** purge consumes the `pending-deletion` referrer and the
  `list_referrers`/`delete_referrer` port methods. **#41 lands first.** Until then this is design
  only.
- **Catalog enumeration limits.** `list_repositories` depends on registry `_catalog` support /
  credentials / pagination (esp. Harbor). The walk surfaces enumeration failure as an error (and
  exits non-zero) rather than reaping a partial, possibly-incomplete candidate set.
- **Oracle correctness is the operator's.** A script that under-reports prod usage causes unsafe
  purges. Mitigations: fail-closed on any oracle error/timeout/unconfigured; dry-run by default; the
  digest key is conservative (§4.1). The oracle's correctness is out of knock's control by design —
  documented prominently in the example.
- **Walk cost on large registries.** O(repos × tags) referrer queries. Mitigated by reusing the
  reconcile concurrency + sharding primitives and the `--registry` bound; called out so the cost is
  not a surprise.

## 13. Open questions (for the plan)

- **Oracle batch interface?** v1 is one `last_prod_usage` call per candidate. If walk volume makes
  per-candidate subprocess spawn costly, a batched `last_prod_usage(list[UsageQuery])` (one process,
  many lines of stdin/stdout) is a forward-compatible refinement — note it, don't build it yet.
- **`--repo` / `--policy` filters.** Deferred; `--registry` covers the v1 need. Add when a real run
  needs finer bounding.

## 14. As-built notes (post-implementation reconciliation)

Shipped per [ADR 0013](../../architecture/decisions/0013-purge-reaper.md). Deltas from the design above, recorded so the spec does not drift from the code:

- **`decide_purge` takes primitives, not `UsageObservation`.** Shipped: `decide_purge(last_seen: datetime | None, *, observed: bool)`. The codebase invariant is that `domain/` never imports `ports/`; the use case bridges the oracle's `UsageObservation` into these primitives (mirroring how `use_cases/reconcile.py` bridges `ImageInfo` via `to_source_artifact`). Supersedes the §5 `decide_purge(observation)` sketch.
- **`parse_pending_mark` lives in `domain/lifecycle.py`** — beside #41's `build_pending_deletion_annotations` writer (not in `domain/purge.py`) — so a round-trip unit test guarantees read/write key parity. The writer is keyword-only with `import_name`; the shared constant is `PENDING_DELETION_ARTIFACT_TYPE`.
- **Reporting is a self-contained `PurgeReport`/`PurgeOutcome`** (Pydantic) rendered by the CLI, **not** the policy-centric `Reporter`. §6.4's proposal to extend `OperationKind`/`Counts` was intentionally dropped: it would couple the reaper to reconcile's event surface, against the discipline-B isolation this design requires. The C4 model carries no `ucPurge → Reporter` edge.
- **`KNOCK_DRY_RUN_DELETIONS` is honoured as the second mutation gate** (§3): the CLI computes `effective_apply = apply and not settings.dry_run_deletions`, so the env var forces dry-run even with `--apply`.
- **`marked_at` / mark-`reason` are parsed but not separately emitted in v1.** `parse_pending_mark` extracts the full mark (identity + `marked_at` + `reason`); the v1 `PurgeOutcome.reason` carries the **oracle's** `detail` (the more actionable "why"). Surfacing `marked_at` for audit is a cheap follow-up, not a v1 deliverable.
- **`RegctlAdapter.list_repositories` treats a `NAME_UNKNOWN` registry as empty** (`[]` → zero candidates → nothing purged; mirrors `list_tags`). Genuine access/pagination failures still raise `RegctlError` and abort the walk (§6.3/§12) — only the benign "registry has no repos yet" case is swallowed.
- **The catalog walk is sequential in v1.** The concurrency/sharding reuse noted in §4 is deferred; `purge_marks` is structured to adopt it without reshaping.
