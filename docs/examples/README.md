# Trying houba locally

These examples let you run `houba reconcile` end-to-end against a **local registry**,
on the **copy path** (mirror + stamp; the BuildKit hardening/rebuild path is a later phase).

What you'll see: houba selects tags from a public source, copies them into your local
registry, sets the derived moving-tag **aliases** (`1.37`, `latest`, …), and writes a
portable **provenance stamp** (OCI annotations) onto each mirrored artifact. Re-running is
idempotent — unchanged tags are skipped via the recorded `base.digest`.

## Prerequisites

- **houba** — `uv run houba version` should print `0.2.0`.
- **[regctl](https://github.com/regclient/regclient/blob/main/docs/install.md)** on your `PATH` — houba shells out to it for all registry operations.
- **Docker** (or Podman) — to run a throwaway local registry.

> **Docker Hub rate limits.** Pulls from `docker.io` are rate-limited when anonymous. If a
> reconcile fails with `429 / toomanyrequests`, authenticate: in the kind demo run
> `DOCKER_USER=<user> DOCKER_PASS=<token> make docker-auth` to seed the optional
> `houba-docker-config` secret with an inline-auth Docker config — both the copy (regctl) and
> rebuild (buildctl) paths then pull authenticated.

## 1. Start a local destination registry

```bash
docker run -d -p 5001:5000 --name houba-demo-registry registry:2
```

The standard `registry:2` serves **HTTP**. Set `tls_verify: false` in the registry entry
below and houba will run `regctl registry set … --tls disabled` automatically before
reconciling. *(Real registries use HTTPS and need no such step.)*

## 2. Point houba at the registry

The roster maps the logical registry names used in a policy's `destinations[].registry`
to real hosts. With a single registry configured, policies may omit `registry` entirely.

```bash
export HOUBA_REGISTRIES='{"local": {"host": "localhost:5001", "tls_verify": false}}'
```

(Credentials would go here too — `"username"` / `"password"` — but a local `registry:2`
is anonymous, so we leave them out.)

## 3. Dry-run, then reconcile

Plan first (no copies, no deletes):

```bash
uv run houba reconcile docs/examples/reference/busybox --dry-run
```

Then for real:

```bash
uv run houba reconcile docs/examples/reference/busybox
# ✓ busybox  imported=12 updated=0 deleted=0 aliased=3 skipped=0
# reconcile [apply] status=ok  imported=12 updated=0 deleted=0 aliased=3 skipped=0 failed_policies=0
```
(Per-operation detail goes to **stderr** as a structlog event journal; pass `--verbose` to
also unfold it in the stdout recap. `HOUBA_LOG_FORMAT=json` switches both streams to JSON.)

(`reconcile` takes a **directory** and discovers policies recursively — so
`uv run houba reconcile docs/examples/reference` reconciles *both* the busybox copy **and**
the debian-tz rebuild (the latter needs a BuildKit daemon). We point at the
`reference/busybox` subdirectory here to keep the quick walkthrough fast, copy-only, and
BuildKit-free.)

## 4. Look at what landed

The mirrored tags + the derived aliases:

```bash
regctl tag ls localhost:5001/demo/busybox
# 1.36  1.36.0  1.36.1 …  1.37  1.37.0 …  latest
```

The provenance stamp on a mirrored artifact (the OCI annotations a scanner reads — note
they sit on the **index** for a multi-arch image):

```bash
regctl manifest get localhost:5001/demo/busybox:1.37.0 --format '{{json .}}' \
  | python3 -c 'import sys,json; print(json.dumps(json.load(sys.stdin)["annotations"], indent=2))'
```

```jsonc
{
  "org.opencontainers.image.source": "docker.io/library/busybox",
  "org.opencontainers.image.base.name": "docker.io/library/busybox:1.37.0",
  "org.opencontainers.image.base.digest": "sha256:9532…",   // the source digest = idempotency key
  // org.opencontainers.image.revision is omitted here because the busybox upstream image
  // declares no revision annotation or label.  When the source *does* declare one,
  // houba propagates it verbatim (manifest annotation wins over config label).
  "org.opencontainers.image.created": "2026-…",
  "io.houba.policy": "busybox",
  "io.houba.import": "stable",
  "io.houba.variant": "default",
  "io.houba.owners": "group:default/platform",
  "io.houba.artifact.type": "image"
}
```

The whole point: when a CVE drops, `base.digest` + `io.houba.owners` make
blast-radius a single annotation query (owners is a comma-joined list of Backstage entity-ref
strings, so an image can appear under several owners).

## 5. Idempotency

Run `reconcile` again — nothing is re-copied, because each mirror artifact's recorded
`base.digest` already matches the current source digest:

```bash
uv run houba reconcile docs/examples/reference/busybox
# ✓ busybox  imported=0 updated=0 deleted=0 aliased=3 skipped=12
# reconcile [apply] status=ok  imported=0 updated=0 deleted=0 aliased=3 skipped=12 failed_policies=0
#                                                                          (aliases are re-pointed every run)
```

## 6. Clean up

```bash
docker rm -f houba-demo-registry
```

---

## The examples

**[`reference/`](reference/)** is **the** policy the reference deployment reconciles — both
`make demo` (the Argo App-of-Apps) and `make local` (the inner-loop overlay) run it — see the
[Reference](../architecture/_export/structurizr-DeployReference.mmd) and
[Local](../architecture/_export/structurizr-DeployLocal.mmd) deployment views. One reconcile
demonstrates **copy *and* rebuild** in a single, self-contained pass (no Harbor, no org config):

- **[`reference/busybox/`](reference/busybox/busybox.yml)** — the **copy path**: select
  `1.36.x`/`1.37.x`, alias `{major}.{minor}` + `latest`, mirror into `demo/busybox`. The smallest,
  fastest case, and the one the walkthrough above runs.
- **[`reference/debian-tz/`](reference/debian-tz/debian-tz.yml)** — the **rebuild path, runnable
  self-contained**: rebuild `debian:bookworm-slim` through `setTimezone` (the one built-in step that
  needs no org config) and fan it into **`-eu` / `-us` variants** via the per-variant `suffix` (the
  worked example of `variants`), stamped into `demo/debian`.

The remaining examples are **standalone feature docs** — each is a `MirrorPolicy` demonstrating one
capability, runnable on its own with `uv run houba …` (not part of the bundled demo):

- **[`redis/redis.yml`](redis/redis.yml)** — semver selection over a real image (`7.2.x`),
  showing how aliases track the highest patch per minor (`7.2` → the latest `7.2.z`) and
  `latest` → the highest overall. Larger image, slower to copy:
  `uv run houba reconcile docs/examples/redis`.
- **[`hardened/redis.yml`](hardened/redis.yml)** — the **rebuild path with org hardening**: inject
  internal CA certs (`injectCA`) + rewrite package sources to an internal mirror, then stamp the
  result. The transform engine is implemented; running it needs a BuildKit daemon (`buildctl`) plus
  the org's `HOUBA_TRANSFORM_CA_CERTS` / `HOUBA_TRANSFORM_PACKAGE_MIRRORS` config (which is why the
  self-contained demo uses the simpler `setTimezone` rebuild instead). Design:
  [the transform/hardening spec](../superpowers/specs/2026-06-11-image-transform-hardening-design.md).
- **[`attested/redis.yml`](attested/redis.yml)** — the **rebuild path, signed**: the same
  hardening rebuild as `hardened/`, but with attestation enabled so the output carries two
  in-toto attestations — BuildKit's `slsa.dev/provenance/v1` and houba's
  `https://houba.dev/predicate/transform/v1`. **Requires the attestation path**: set
  `HOUBA_ATTEST_SIGNER` (`keyless` | `kms` | `key`) and a `cosign` on `PATH`; off by default.
  Design: [the SLSA/in-toto attestation spec](../superpowers/specs/2026-06-11-slsa-attestation-design.md).
  Note: with complete attestation coverage, attestation is not limited to the rebuild path.
  The **copy path** (no transform) and **already-mirrored images** (backfill) are also signed when
  an attestor is configured — every image houba fronts carries a signed houba attestation.
- **[`pending-deletion/pending-deletion.yml`](pending-deletion/pending-deletion.yml)** —
  `deletionMode: mark`: when a tag drops out of the selection, houba attaches a
  `pending-deletion` OCI referrer instead of deleting it. See
  [Pending-deletion (delegated deletion)](#pending-deletion-delegated-deletion) below.
- **[`retention/redis.yml`](retention/redis.yml)** — **retention-driven soft-delete**: cap
  *valid, in-selection* tags with `archive: {keep, olderThanDays}`. houba keeps the N most-recently
  imported tags of each stream and marks the older surplus `pending-deletion`
  (reason `retention-excess`) for the reaper — the one axis selection filtering can't reach. See
  [Retention (capping valid tags)](#retention-capping-valid-tags) below.
- **[`oracles/datadog.sh`](oracles/datadog.sh)** — reference usage oracle for `houba purge`.
  See [houba purge — the reference reaper](#houba-purge--the-reference-reaper) below.
- **[`scan/README.md`](scan/README.md)** — the **`houba attach` path**: ingest an
  upstream SARIF report and stamp it as a portable OCI referrer on the image's digest —
  also signed as an in-toto scan attestation when `HOUBA_ATTEST_SIGNER` is set.
  houba does not run a scanner — the scan is produced upstream (CI, registry-native
  scanner, or scan service) and handed in. `scan/sample.sarif.json` is a runnable
  example report (1 critical CVE, 1 medium).

### Pending-deletion (delegated deletion)

`pending-deletion/pending-deletion.yml` sets `deletionMode: mark`. When a tag drops out of the
selection, houba does **not** delete it — it attaches a `pending-deletion` OCI referrer
(`application/vnd.houba.lifecycle.pending+json`, carrying `io.houba.lifecycle.marked-at` /
`io.houba.lifecycle.reason` / `io.houba.lifecycle.state` and the policy/import identity).
The digest is unchanged and the tag stays pullable. An external reaper lists these referrers,
checks production usage, and purges. If the tag re-enters the selection on a later run, houba
clears the mark. If `deletionMode` is later removed or changed to `purge`, the next reconcile
hard-deletes any still-undesired tags (the stale marks become moot).

Resolution is a cascade (most-specific wins): `deletionMode` on the policy wins, else the
destination's `deletion_mode` (in `HOUBA_REGISTRIES`), else the global `HOUBA_DELETION_MODE`
(default `purge`).

### houba purge — the reference reaper

`houba purge` is the shipped reference implementation of the reaper role introduced by
[delegated tag deletion (ADR 0012)](../architecture/decisions/0012-delegated-tag-deletion.md).
It is isolated behind its own `UsageOraclePort` and is fully replaceable — if you already
have a reaper, `deletionMode: mark` still works; just don't run `houba purge`.

**The lifecycle of a purged tag:**

1. A tag falls out of its policy selection (e.g. a version is removed from the semver range).
   With `deletionMode: mark`, `houba reconcile` attaches a `pending-deletion` OCI referrer to
   the tag instead of hard-deleting it. The digest is unchanged and the tag stays pullable.

2. Run `houba purge` in **dry-run mode** (the default — no deletes happen):

   ```bash
   uv run houba purge
   # protect  myimage:old-tag  reason=prod_sighting  last_seen=2026-06-12T14:05:00Z
   ```

   While the tag's digest is still seen in production (within `HOUBA_PURGE_MIN_IDLE_DAYS`),
   purge reports it as `protect` — nothing is removed.

3. After `HOUBA_PURGE_MIN_IDLE_DAYS` pass with no production sighting, a subsequent dry run
   shows the tag as `purge`:

   ```bash
   uv run houba purge
   # purge  myimage:old-tag  idle_since=2026-06-06T14:05:00Z
   ```

4. Apply the purge (removes the tag and clears the `pending-deletion` mark):

   ```bash
   uv run houba purge --apply
   # purge  myimage:old-tag  [deleted]
   ```

**Fail-closed.** If the usage oracle errors, times out, or returns an unparseable answer for a
candidate, `houba purge` treats that candidate as **still in use**: it protects the tag (never
deletes it) and continues to the next candidate. A flaky oracle can therefore only ever *spare*
tags, never trigger a mass purge of potentially live images. (If `HOUBA_USAGE_ORACLE_CMD` is not
configured at all, purge refuses to start — exit 3 — rather than run blind.)

**Oracle is replaceable.** Set `HOUBA_USAGE_ORACLE_CMD` to any executable that speaks the
contract: reads a JSON object from stdin (`{"digest","image_ref","identity","since"}`) and
writes `{"last_seen": "<ISO timestamp or null>"}` to stdout. The reference implementation
for Datadog is at [`oracles/datadog.sh`](oracles/datadog.sh) — adapt the Datadog API call
to your setup (endpoint, metric/log query, environment tag).

**Required config:**

```bash
export HOUBA_PURGE_MIN_IDLE_DAYS=7          # idle window before a tag is eligible
export HOUBA_USAGE_ORACLE_CMD=docs/examples/oracles/datadog.sh
# plus DD_API_KEY, DD_APP_KEY, DD_SITE for the Datadog oracle
```

Both variables are required; missing either raises a `ConfigError` (exit code 3) before
touching the registry.

### Retention (capping valid tags)

`pending-deletion` (above) and the reaper handle tags that *fall out of selection*. **Retention**
handles the opposite problem: tags that stay perfectly *valid* but pile up forever — a policy that
mirrors every patch (`includeRegex: "^7\\.2\\."`) keeps accumulating `7.2.z` tags, each still in
selection, so the selection axis never touches them.

[`retention/redis.yml`](retention/redis.yml) activates the `archive` knobs to cap them:

```yaml
archive:
  keep: 3            # always retain the 3 most-recently-imported 7.2.* tags
  olderThanDays: 30  # of the rest, mark only those older than 30 days
```

During `reconcile`, houba ranks each stream's in-selection tags by **import time** (houba's own
stamp, `org.opencontainers.image.created`), keeps the `keep` newest, and attaches a
`pending-deletion` referrer (reason `retention-excess`) to any older tag beyond that count — both
conditions must hold (`keep` **and** `olderThanDays`). Alias targets (e.g. whatever `latest` points
at) are never marked, and a mark clears automatically if the tag stops being excess on a later run.

Retention **only ever marks** — it never hard-deletes, even under `deletionMode: purge`: removing a
*valid* tag must always pass the usage gate. So retention presupposes a scheduled **`houba purge`**
(above); without one, marks accumulate harmlessly and the tags stay fully pullable.

Thresholds cascade **global ← policy**, per field: a fleet-wide default in `HOUBA_RETENTION`
(a JSON `Archive` object) is refined by a policy's `archive:`. With neither set, retention is off
and behaviour is unchanged.

```bash
# fleet-wide default (optional); a policy's `archive:` overrides it per field
export HOUBA_RETENTION='{"keep": 5, "olderThanDays": 90}'
```

### Transform vocabulary

Hardening steps are pluggable primitives: `injectCA`, `rewritePackageSources`, and
`setTimezone` (e.g. `setTimezone: { zone: Europe/Paris }`). Adding a primitive is a
single self-contained compiler in `houba/domain/transforms/steps.py`.

### Signed attestations (SLSA / in-toto)

On the **rebuild path**, houba can additionally **sign** the result. Set
`HOUBA_ATTEST_SIGNER` to `keyless`, `kms`, or `key` (default `""` = off, no attestation —
exactly like an empty `HOUBA_LABEL_PREFIX` emits no labels) and ensure `cosign` is on `PATH`.
Two attestations are produced, attached to the image digest as OCI referrers:

- **`https://slsa.dev/provenance/v1`** — emitted by BuildKit (the build facts). houba only
  enables it (`--opt attest:provenance=mode=max`).
- **`https://houba.dev/predicate/transform/v1`** — houba's transform/hardening lineage
  (which policy/import/variant, the source digest, the resolved steps, the builder id),
  signed via the configured signer.

Trust is org configuration, never baked in: `keyless` uses Fulcio + an OIDC identity
(point `HOUBA_ATTEST_FULCIO_URL` at an internal CA if you run one); `kms`/`key` sign with
`HOUBA_ATTEST_KEY_REF` (a KMS URI or a key path). A blank `HOUBA_ATTEST_REKOR_URL` writes
**no transparency-log entry** — the air-gapped path. See [`attested/redis.yml`](attested/redis.yml).

The **same signer** also covers the **`houba attach` path**: with `HOUBA_ATTEST_SIGNER` set, each
ingested scan result is attached *both* as the raw SARIF referrer *and* as a signed in-toto
attestation (`https://houba.dev/predicate/scan/v1`) over the image digest — so a downstream
admission controller can *require* a signed scan, not merely read an annotation. Pure copies (no
rebuild, no scan) stay at the annotation layer.

### Coverage audit (houba audit)

Once images are flowing through houba, **`houba audit`** answers the coverage-gate question:
*which images in the registry do NOT carry houba's provenance stamp?* It walks the configured
registries (or a single `--registry NAME`), reads each image's annotations, and reports each as
covered or uncovered — the blind-spot report that makes the front door verifiable.

```bash
# after a reconcile, against the local registry:2 from the walkthrough above
uv run houba audit
# UNCOVERED localhost:5001/demo/other-image:latest
# audit  scanned=13 covered=12 uncovered=1 errored=0
```

It is **read-only** (never deletes or stamps) and **report-only by default** (exit 0). For a CI
gate, pass `--fail-on-uncovered` to exit non-zero when any image lacks the stamp:

```bash
uv run houba audit --fail-on-uncovered    # exit 1 if uncovered > 0
```

An image counts as covered when it carries the houba lineage annotation (`io.houba.policy`, or
the OCI `org.opencontainers.image.base.digest` when `HOUBA_LABEL_PREFIX` is empty). `HOUBA_LOG_FORMAT=json`
emits the full structured `CoverageReport`.

For the **trustworthiness tier**, add `--signed`: for each *stamped* image it also probes for a
signed attestation referrer (a present cosign bundle ⇒ signed; no pull-and-verify), distinguishing
*signed* from *merely stamped*:

```bash
uv run houba audit --signed
# UNSIGNED  localhost:5001/demo/legacy-image:latest
# audit  scanned=13 covered=12 uncovered=1 signed=11 unsigned=1 errored=0
```

As a CI gate, `--fail-on-unsigned` exits non-zero when any stamped image is unsigned (it implies
`--signed`):

```bash
uv run houba audit --fail-on-unsigned    # exit 1 if unsigned > 0
```

### Upgrade note

The `io.houba.transform.version` hash format changed when the pluggable registry landed;
on the first reconcile after upgrading, already-hardened images rebuild **once** (their
recorded version no longer matches), then stay idempotent.

The copy-path examples keep `registry` off the destinations (resolved to the single
configured `local` registry), so they stay portable — the same policy file works against
any registry roster.

> **One repository per policy.** Each destination repository must be owned by exactly one `MirrorPolicy` —
> two policies writing the same repo is rejected at load time (they would mutually delete each other's
> tags). This is also what makes horizontal sharding safe (one writer per repo).

> A policy is just data. `uv run python -c "import json,houba.domain.mirror_policy as m;
> print(json.dumps(m.MirrorPolicy.model_json_schema(), indent=2))"` prints the JSON Schema
> if you want editor validation.
