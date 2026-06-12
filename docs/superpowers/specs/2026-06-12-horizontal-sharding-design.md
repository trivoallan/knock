# Horizontal sharding — scale-out across pods

- **Date:** 2026-06-12
- **Status:** approved (design), not yet implemented
- **Scope:** a pure shard-selection function + a global ownership invariant in `domain/`; a filter step in `use_cases/reconcile.py`; two CLI flags; the reference CronJob → Indexed Job. Companion to the [concurrent reconcile spec](2026-06-12-concurrent-reconcile-design.md).

## Context & motivation

houba runs today as a **single Kubernetes CronJob** (`deploy/base/cronjob-reconcile.yaml`), hourly,
`concurrencyPolicy: Forbid`, one pod reconciling **all** policies; `buildkitd` is a `replicas: 1`
Deployment. That is strictly single-instance: safe (no overlap), but it does not scale out.

The companion threading spec is the **scale-up** axis (parallel *tags* within one pod). This spec is the
**scale-out** axis (parallel *policies* across pods). They compose: a sharded pod owns a subset of policies
and threads the tags within each.

houba is already well-positioned for scale-out: it is **stateless**, the **destination registry is the
state store**, reconcile is a **convergence loop** (controller pattern), and per-policy isolation already
exists. The only thing missing is a safe way to divide the policy set across instances without two
instances writing the same destination.

## Goals

1. Let N houba instances each reconcile a **disjoint** subset of policies, with **no cross-instance races**
   on any destination repository.
2. Keep it **stateless and coordination-free** — no distributed lock, no queue, no leader election. The
   registry stays the only state store.
3. Make the safe-concurrency **invariants explicit and enforced** (idempotency; one owner per dest-repo).
4. `N = 1` must be **exactly today's behaviour** (graceful degradation / default).
5. Keep `domain/` pure: shard selection and the ownership invariant are pure functions.

## Non-goals

- **Distributed locking / leases / work-queues** — rejected (see *Decisions*); against the stateless,
  registry-is-state, "not an operator" ethos (roadmap).
- **Multiple policies writing the same dest-repo** — explicitly *forbidden* (the ownership invariant). The
  alternative (policy-scoped deletes keyed on the stamp) is out of scope (see *Future work*).
- **Implementing buildkitd horizontal scaling / build cache** — designed as the target and documented, but
  not built here (see *buildkitd coupling*).
- **Dynamic rebalancing / autoscaling (HPA)** — N is static per Job definition.

## Decisions (with rejected alternatives)

| # | Decision | Rejected alternatives & why |
|---|----------|------------------------------|
| D1 | **Ownership unit: the policy.** `hash(policy.name) % N` selects the shard; a global invariant forbids two policies sharing a dest-repo. | *Shard by dest-repo*: bulletproof isolation without an invariant, but splits multi-destination policies across pods → duplicated upstream source reads + fragmented per-policy reports. The only case it additionally supports (two policies → one repo) is precisely what we want to forbid. |
| D2 | **Spawn: CronJob → Indexed Job** (`completions=N, parallelism=M`, `$JOB_COMPLETION_INDEX`). | *N static CronJobs*: N objects, no shared parallelism cap (a thundering herd on buildkitd at the tick), manual rebalancing. *Work-queue*: needs a queue + coordinator + visibility timeouts — too much machinery for a stamper. |
| D3 | **Coordination-free via disjoint sharding**, not locking. | *Per-repo lease/lock*: would allow any pod to take any policy, but adds a coordination store and TOCTOU windows. Disjoint single-owner sharding removes delete-TOCTOU **and** the 7-day-window clock-skew problem for free. |
| D4 | **Stable hash = `hashlib.sha256`**, not Python's builtin `hash()`. | Builtin `hash()` is **per-process salted** (`PYTHONHASHSEED`) → different pods would disagree on ownership → gaps and double-writes. A cryptographic digest is stable across pods and Python versions. |
| D5 | **buildkitd: design scalable, ship without it.** | Build-path parallelism (in-pod threads *and* cross-pod shards) is capped by buildkitd capacity. Scaling it (replicas + Service + registry cache) is the documented target, but the copy path scales immediately, so we don't block on it. |

## Architecture — ownership model

**Sharding filters what a pod *applies*, not what it *sees*.** Every pod's `git-sync` init container clones
the full policy repo, so every pod sees all policies. Each pod then:

1. **Resolves dest-repos for ALL policies** — pure, **no registry I/O** (it uses `resolve_imports` +
   `resolve_registry` on the policy spec + roster; it does **not** call `expand_import`, which would need
   source tags). Runs the **global ownership invariant**: no dest-repo claimed by > 1 policy. Fail-fast,
   before any mutation, identically in every pod.
2. **Filters** policies to the ones it owns: `owns(name, shard_index, shard_count)`.
3. Runs the **existing** expensive plan+apply (the threading spec's pipeline) over the owned subset only —
   so the costly `list_tags`/`inspect`/build/copy work, and the upstream source reads, happen only for
   this shard's policies.

This preserves sharding's two benefits: disjoint write-isolation (no two pods touch the same repo) **and**
no duplicated upstream load.

### Shard-selection function (pure, `domain/sharding.py`)

```python
import hashlib

def policy_shard(name: str, *, shard_count: int) -> int:
    """Stable shard index for a policy name. Uses sha256 — NOT builtin hash(),
    which is per-process salted (PYTHONHASHSEED) and would make pods disagree."""
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count

def owns(name: str, *, shard_index: int, shard_count: int) -> bool:
    return policy_shard(name, shard_count=shard_count) == shard_index
```

### Global ownership invariant (pure, `domain/collision.py`)

A new sibling of `detect_alias_collisions`: given `(dest_repo, policy_name)` pairs for the **full** policy
set, raise a collision `DomainError` (exit 1) if any `dest_repo` is claimed by more than one policy. This
is **not a new constraint** — two policies on one repo already mutually delete each other's tags every run
(reconcile is authoritative per repo), so it is a latent misconfiguration today that sharding forces us to
make explicit and enforce.

## Execution flow (restructured `reconcile_policies`)

`reconcile_policies(policies, ..., shard_index=0, shard_count=1)`:

```
# 1. Global ownership invariant over ALL policies (pure, no I/O), fail-fast.
owners = [(dest_repo, policy.metadata.name)
          for policy in policies
          for dest_repo in _resolved_dest_repos(policy, roster)]   # resolve_imports + resolve_registry
detect_dest_repo_collisions(owners)

# 2. Filter to this shard.
owned = [p for p in policies if owns(p.metadata.name, shard_index=shard_index, shard_count=shard_count)]

# 3. Existing plan + apply (the threading pipeline) over `owned` only — unchanged.
#    detect_alias_collisions still runs, now over owned policies' alias entries
#    (cross-policy/cross-repo collisions are already excluded by the ownership invariant).
```

`shard_count == 1` ⇒ `owned == policies` ⇒ byte-for-byte today's behaviour.

> A malformed policy (e.g. unknown registry) fails dest-repo resolution and therefore fails the run in
> **every** pod — consistent with today's single-process behaviour, where one bad policy fails the whole
> run. The "front door" should not run half-validated.

## Correctness invariants (the backbone, true regardless of N)

- **Idempotency.** `copy` (push by digest), `annotate` (set/overwrite manifest annotations), and `alias`
  (tag overwrite) are idempotent → a re-run, a retry, or an overlapping run **converges** without
  corruption.
- **Delete-safety.** Deletes are **authoritative per repo** (a policy deletes any tag in its dest-repo it
  does not desire). Under the ownership invariant + disjoint sharding, **each repo has exactly one writer**,
  so there is no concurrent importer to race the delete against → the TOCTOU disappears. `Forbid` keeps a
  pod's own next tick from overlapping it.
- **No clock-skew divergence.** The 7-day digest-stability window depends on `now()` + registry state; with
  one owner per repo, no two instances ever decide about the same artifact, so skew between pods is moot.

These are asserted with tests (below), not just assumed.

## CLI

`houba reconcile <dir>` gains two integer options (no env reading in app code — the manifest passes them via
the shell, honouring "`config.py` is the only env reader"):

```python
shard_index: Annotated[int, typer.Option("--shard-index", min=0,
    help="This shard's 0-based index (pass $JOB_COMPLETION_INDEX in an Indexed Job).")] = 0,
shard_count: Annotated[int, typer.Option("--shard-count", min=1,
    help="Total number of shards N (1 = process all policies).")] = 1,
```

Validate `shard_index < shard_count` (raise a `ConfigError`/typer error otherwise). Pass both into
`reconcile_policies`.

## Kubernetes — CronJob → Indexed Job

`deploy/base/cronjob-reconcile.yaml`, `jobTemplate.spec` gains:

```yaml
      completionMode: Indexed
      completions: 1        # = N shards. Bumped per overlay; MUST equal SHARD_COUNT below.
      parallelism: 1        # = M concurrent pods (M ≤ N; cap to protect buildkitd).
```

The houba container args become (shell expands the kube-injected `$JOB_COMPLETION_INDEX` and the
config-map `$SHARD_COUNT` — houba never reads them itself):

```yaml
args: ['exec houba reconcile "$POLICY_DIR" --shard-index "$JOB_COMPLETION_INDEX" --shard-count "$SHARD_COUNT"']
```

- `JOB_COMPLETION_INDEX` is injected automatically by Kubernetes into Indexed-Job pods.
- `SHARD_COUNT` is a `houba-config` ConfigMap value; **it must equal `completions`** — both are N, set from
  one place (a kustomize variable or a single ConfigMap key) so they cannot drift.
- `concurrencyPolicy: Forbid` is unchanged → no overlap of successive Jobs.
- `backoffLimit: 0` is unchanged (a failed shard waits for the next schedule). Indexed mode additionally
  tracks per-index completion, so bumping `backoffLimit` later retries only failed shards.
- `git-sync` runs per pod into its own `emptyDir` → every pod sees the full policy set (needed for the
  global invariant). No shared volume across pods.
- **Base stays `completions: 1, parallelism: 1`** (= today). Overlays bump N/M.

## buildkitd coupling (target, deferred)

The build path (`build_and_push`) terminates at `buildkitd`. One daemon interleaves builds up to one
node's resources; exceeding that needs `replicas > 1`. The target:

- buildkitd `replicas` becomes an overlay knob; houba pods reach it via the existing buildkitd **Service**
  (load-balanced).
- Cache fragmentation across replicas is mitigated by a **registry-backed cache** (`buildctl … --export-cache
  type=registry --import-cache type=registry`) — a change in the `buildkit_cli` adapter.

Not built here. Until then `--shard-count` and `max_concurrency` scale the **copy** path; the build-path
ceiling is the single buildkitd. `max_concurrency` default stays modest (4).

## Code touch points

- **Create** `houba/domain/sharding.py` — `policy_shard`, `owns` (pure).
- **Modify** `houba/domain/collision.py` — add `detect_dest_repo_collisions` (pure).
- **Modify** `houba/use_cases/reconcile.py` — `_resolved_dest_repos` helper (pure resolution), the global
  invariant call, the shard filter, and `shard_index`/`shard_count` params on `reconcile_policies`.
- **Modify** `houba/cli/reconcile.py` — `--shard-index` / `--shard-count`, `shard_index < shard_count`
  validation, pass-through.
- **Modify** `deploy/base/cronjob-reconcile.yaml` (+ `houba-config` ConfigMap) — Indexed Job, `SHARD_COUNT`.
- **Docs** — `docs/runbooks/reference-deployment.md` (sharding section), `docs/architecture/README.md`
  wording (CronJob → optionally-sharded Indexed Job).

## C4 / examples impact

- **C4 (`docs/architecture/workspace.dsl`):** **no change.** Sharding adds no actor, external system, or
  integration; it is an internal deployment-topology detail, invisible at the System Context / System
  Landscape levels the model covers.
- **Examples (`docs/examples/`):** **no `MirrorPolicy` change.** Sharding is a runtime/deploy concern, not
  policy schema. The ownership invariant may surface as a documented constraint ("one dest-repo per
  policy") in the examples README.

## Testing strategy

Pure-domain unit tests (≥ 90 % coverage applies to `domain/`):

1. **`policy_shard` is stable and balanced** — fixed name → fixed index across calls; the partition of a
   sample name set is disjoint and covers `0..N-1` reasonably. **Explicitly assert independence from
   `PYTHONHASHSEED`** (the value must not be Python's builtin `hash`).
2. **`owns` partitions** — for a set of names, every name is owned by exactly one shard across `0..N-1`,
   and `shard_count == 1` ⇒ everything owned.
3. **`detect_dest_repo_collisions`** — raises on two policies sharing a dest-repo; passes when disjoint.

Use-case tests (fakes, in-memory):

4. **Shard filter** — with `shard_count > 1`, only owned policies are applied (assert via the journalled
   fake registry: no copies/inspects for non-owned policies' repos); union of all shards = the
   single-shard run.
5. **Global invariant runs before filtering** — a dest-repo collision fails **every** shard, before any
   mutation (no copies recorded).
6. **`shard_count == 1` parity** — identical `RunReport` to today.
7. **Idempotency / delete-safety** — realised as a *domain property*, not a stateful-fake use-case test:
   `reconcile_import` already returns empty import/update/delete sets when the mirror matches the source
   within the stability window (covered by `tests/unit/domain/test_reconcile.py`), and the adapter ops
   (`copy` by digest, `annotate`/`alias` overwrite) are idempotent. Under the ownership invariant (item 3),
   each repo has a single writer, so a delete has no concurrent importer to race. We assert the invariant and
   rely on the existing domain convergence tests.

Strict TDD per house rule: failing test → red → minimal impl → green → commit, one behaviour per commit.

## Out of scope / future work

- **Policy-scoped deletes** (delete only tags whose stamp `policy=` matches) → would safely allow multiple
  policies per dest-repo, lifting the ownership invariant. Bigger change to the delete logic.
- **buildkitd horizontal scaling + registry build cache** — the target above, deferred.
- **Dynamic rebalancing / autoscaling** — N is static per Job; changing N is a manifest edit.
- **Cross-shard run aggregation** — each shard emits its own `RunReport`; a combined fleet view (e.g. the
  blast-radius consumer reading stamps) is a separate concern, already out of houba's scope per the roadmap.
