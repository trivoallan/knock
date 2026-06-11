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

## 1. Start a local destination registry

```bash
docker run -d -p 5001:5000 --name houba-demo-registry registry:2
```

The standard `registry:2` serves **HTTP**, so tell regctl not to use TLS for it. *(This
is a one-time local-registry quirk — houba doesn't yet configure per-registry TLS/auth
itself; that's wired in a later phase. Real registries use HTTPS and need no such step.)*

```bash
regctl registry set localhost:5001 --tls disabled
```

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
# reconcile: imported=12 updated=0 deleted=0 aliased=3
```

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
# reconcile: imported=0 updated=0 deleted=0 aliased=3   (aliases are re-pointed every run)
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

Both keep `registry` off the destinations (resolved to the single configured `local`
registry), so they stay portable — the same policy file works against any registry roster.

> A policy is just data. `uv run python -c "import json,houba.domain.mirror_policy as m;
> print(json.dumps(m.MirrorPolicy.model_json_schema(), indent=2))"` prints the JSON Schema
> if you want editor validation.
