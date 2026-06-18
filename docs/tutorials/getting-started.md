# Getting started

Run `houba reconcile` end-to-end against a **local registry** in about ten minutes — from
nothing to a stamped image you can inspect. This is the **copy path** (mirror + stamp; the
BuildKit hardening/rebuild path is shown in the [examples](/examples)).

What you'll see: houba selects tags from a public source, copies them into your local
registry, sets the derived moving-tag **aliases** (`1.37`, `latest`, …), and writes a
portable **provenance stamp** (OCI annotations) onto each mirrored artifact. Re-running is
idempotent — unchanged tags are skipped via the recorded `base.digest`.

## Prerequisites

- **houba** — `uv run houba version` should print `0.7.0`.
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
# 1.37  1.37.0  1.38  1.38.0  latest
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

**Next:** the [example policies](/examples) catalog — semver selection, the
[rebuild/hardening path](../how-to/rebuild-and-harden.md), retention, delegated deletion, `houba purge`, scan ingestion, and the
coverage audit, each a runnable `MirrorPolicy` demonstrating one capability. For every field and
every `HOUBA_*` variable, see the generated [policy](../reference/schemas/mirror-policy.md) and
[config](../reference/configuration.md) reference.
