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
uv run houba reconcile docs/examples/busybox --dry-run
```

Then for real:

```bash
uv run houba reconcile docs/examples/busybox
# ✓ busybox  imported=12 updated=0 deleted=0 aliased=3 skipped=0
# reconcile [apply] status=ok  imported=12 updated=0 deleted=0 aliased=3 skipped=0 failed_policies=0
```
(Per-operation detail goes to **stderr** as a structlog event journal; pass `--verbose` to
also unfold it in the stdout recap. `HOUBA_LOG_FORMAT=json` switches both streams to JSON.)

(`reconcile` takes a **directory** and discovers policies recursively — so
`uv run houba reconcile docs/examples` would reconcile *both* busybox and redis.
We point at the `busybox/` subdir here to keep the quick walkthrough fast and predictable.)

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
  "org.opencontainers.image.revision": "sha256:9532…",
  "org.opencontainers.image.created": "2026-…",
  "io.houba.policy": "busybox",
  "io.houba.import": "stable",
  "io.houba.variant": "default",
  "io.houba.owner.team": "platform",
  "io.houba.artifact.type": "image"
}
```

The whole point: when a CVE drops, `base.digest` + `io.houba.owner.team` make
blast-radius a single annotation query.

## 5. Idempotency

Run `reconcile` again — nothing is re-copied, because each mirror artifact's recorded
`base.digest` already matches the current source digest:

```bash
uv run houba reconcile docs/examples/busybox
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

- **[`busybox/busybox.yml`](busybox/busybox.yml)** — the smallest, fastest case: select
  `1.36.x`/`1.37.x`, alias `{major}.{minor}` + `latest`, mirror into `demo/busybox`. This
  is the one the walkthrough above runs.
- **[`redis/redis.yml`](redis/redis.yml)** — semver selection over a real image (`7.2.x`),
  showing how aliases track the highest patch per minor (`7.2` → the latest `7.2.z`) and
  `latest` → the highest overall. Larger image, slower to copy:
  `uv run houba reconcile docs/examples/redis`.
- **[`hardened/redis.yml`](hardened/redis.yml)** — the **rebuild path**: inject internal
  CA certs + rewrite package sources to an internal mirror, then stamp the result. The
  transform engine is implemented; running it needs a BuildKit daemon (`buildctl`) plus the
  org's `HOUBA_TRANSFORM_CA_CERTS` / `HOUBA_TRANSFORM_PACKAGE_MIRRORS` config. Design:
  [the transform/hardening spec](../superpowers/specs/2026-06-11-image-transform-hardening-design.md).
- **[`timezone/debian.yml`](timezone/debian.yml)** — the **rebuild path, runnable
  self-contained** (no Harbor, no org config): rebuild `debian:bookworm-slim` through
  `setTimezone` and fan it into **`-eu` / `-us` variants** via the per-variant
  `suffix` (the first worked example of `variants`). Run it end-to-end in kind with
  `make demo-transform` — see the [`local-transform` overlay](../../deploy/overlays/local-transform).

### Transform vocabulary

Hardening steps are pluggable primitives: `injectCA`, `rewritePackageSources`, and
`setTimezone` (e.g. `setTimezone: { zone: Europe/Paris }`). Adding a primitive is a
single self-contained compiler in `houba/domain/transforms/steps.py`.

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
