# Source-registry credentials — authenticate pulls to dodge rate limits

**Status:** approved (design)
**Date:** 2026-06-12
**Related:** [`2026-06-12-local-transform-demo-design.md`](2026-06-12-local-transform-demo-design.md) (the demo whose `make demo-transform` hit the limit).

## Problem

houba pulls each policy's **source** image anonymously, so high-volume demos and real deployments hit Docker Hub's **unauthenticated pull rate limit (429)** — exactly what blocked the `local-transform` e2e (`buildctl` pulling `debian` returned `toomanyrequests`). The credential model already exists for **destinations** (`RegistryConfig` in `houba/config.py` carries `username`/`password`, and `reconcile` runs `regctl registry login` for each destination host), but the **source registry is never authenticated**.

## Finding (what makes this nearly code-free)

Both source-pulling clients read the **standard Docker `config.json`**:

- `buildctl` (rebuild path) forwards credentials from `$DOCKER_CONFIG/config.json` to buildkitd natively.
- `regctl` (copy path) reads Docker's `config.json` as a credential fallback — its own `registry login` help says *"This may not be necessary if you have already logged in with docker."*

And houba's **destination** logins do **not** collide with a Docker config: `regctl registry set`/`login` persist to regctl's own config, not Docker's. Verified empirically (houba image, `regctl v0.11.5`):

```
DOCKER_CONFIG=/tmp/dockercfg  REGCTL_CONFIG=/tmp/regctlcfg/config.json  regctl registry set localhost:5000 --tls disabled
→ /tmp/regctlcfg/config.json gains the host; /tmp/dockercfg/config.json stays {"auths":{}}
```

So a **read-only Docker `config.json` mounted for source creds** is read by both clients, while destination logins keep writing to a separate, writable `REGCTL_CONFIG`.

## Goal

Let an operator authenticate source pulls by supplying a standard Docker `config.json`, **opt-in**, wired once in `deploy/base` so **every tier** (lite / transform / full / prod) benefits. Absent the secret, behaviour is unchanged (anonymous). **No houba code change**, no policy/example change.

## Design

### `deploy/base/cronjob-reconcile.yaml` — the `houba` container

- **env**
  - `DOCKER_CONFIG=/docker-config` — where `buildctl` and `regctl` look for source creds.
  - `REGCTL_CONFIG=/tmp/.regctl/config.json` — pin regctl's *own* config (destination `registry set`/`login`) to the writable `work` mount, so it never tries to write the read-only Docker config. (This is already regctl's default under `HOME=/tmp`; setting it explicitly makes the separation deterministic regardless of `DOCKER_CONFIG`.)
- **volumeMounts**: `/docker-config` (`readOnly: true`).
- **volumes**: a secret volume from `houba-docker-config`, **`optional: true`**, projecting key `config.json`.

Opt-in semantics: with the secret absent, the optional volume mounts empty → `/docker-config/config.json` does not exist → both clients fall back to anonymous (today's behaviour). With the secret present, both authenticate. `readOnlyRootFilesystem: true` is preserved — the Docker config is a read-only mount, and regctl writes only under `/tmp` via `REGCTL_CONFIG`.

Only the reconcile container is touched: it is the sole component that pulls the **source** (docker.io). The blast-radius Job reads the **destination** registry only, so it is left unchanged.

### The secret

A generic (`Opaque`) secret named `houba-docker-config` with a single key **`config.json`** holding a standard Docker config (`{"auths": {"https://index.docker.io/v1/": {"auth": "<base64 user:pass>"}}}`). A `kubernetes.io/dockerconfigjson`-typed secret is deliberately *not* used: its key is `.dockerconfigjson`, which would not land as `config.json` inside `$DOCKER_CONFIG` without an extra `items` remap.

### Makefile affordance — `make docker-auth`

A one-command way to seed the secret from the operator's existing Docker login:

```make
docker-auth: ## Load your local Docker Hub creds so source pulls are authenticated (avoids rate limits)
	$(KUBECTL) -n $(NS) create secret generic houba-docker-config \
	  --from-file=config.json=$$HOME/.docker/config.json \
	  --dry-run=client -o yaml | $(KUBECTL) apply -f -
```

`make docker-auth && make demo-transform` then pulls `debian` authenticated. Idempotent (apply-from-dry-run). Prerequisite: the operator is logged in locally (`docker login`), so `$HOME/.docker/config.json` exists.

### Docs

- `deploy/overlays/local-transform/README.md`: a note that if you hit Docker Hub rate limits, `make docker-auth` (or creating the `houba-docker-config` secret) authenticates source pulls. (`local-lite` has no README; its walkthrough lives in `docs/examples/README.md`.)
- `docs/examples/README.md`: a short note in the rate-limit-prone walkthrough.

## Non-goals

- No houba application code, no port/adapter change.
- No change to the destination-auth roster (`HOUBA_REGISTRIES`) or its `regctl login` flow.
- No new policy/example (this is deployment config, not a `MirrorPolicy` feature).
- Not modelling source creds inside `HOUBA_REGISTRIES` — the standard Docker config is the credential surface (the operator's choice in design review).

## Architecture sync

- **C4 unchanged, deliberately.** Docker Hub (the source registry) is already an external system in the model and houba already pulls from it; adding authentication is an integration detail, not a new actor/system/integration at context or landscape level. `workspace.dsl` does not drift. (Noted to satisfy the "spec that shifts architecture updates C4" gate — this spec does not shift it.)
- **No examples drift**: the change is deployment wiring, not a user-facing policy feature, so `docs/examples/` policies are untouched (only a rate-limit note is added).

## Testing & verification

No application code, so verification is operational plus the one already-proven fact:

1. **regctl write-target (proven above)**: with `DOCKER_CONFIG` set read-only and `REGCTL_CONFIG` set, regctl's destination `registry set`/`login` writes to `REGCTL_CONFIG` and leaves the Docker config untouched.
2. **Kustomize** — `kubectl kustomize deploy/overlays/local-transform` (and `local-lite`, `local-full`) still render; the rendered reconcile container has `DOCKER_CONFIG`/`REGCTL_CONFIG` env and the optional `houba-docker-config` mount at `/docker-config`.
3. **Opt-in absent** — without the secret, the reconcile Job still starts and runs (anonymous); the optional volume mounts empty.
4. **Opt-in present (end-to-end)** — `make docker-auth` (from a host logged into Docker Hub) then `make demo-transform`: the `debian` base pull is **authenticated** and the rebuild completes past the point that previously returned 429. Equivalently for the copy path, `make demo-lite` keeps working with the secret present (regctl uses the Docker config for docker.io).

## Risks

- **Docker config format** — must be a valid Docker `config.json` with an `auths` entry for `https://index.docker.io/v1/`. `make docker-auth` copies the operator's working one, sidestepping hand-authoring.
- **Stale/expired creds** — an invalid `config.json` makes pulls fail differently than anonymous; documented in the rate-limit note.
- **`optional: true` reliance** — the base must keep the secret volume optional so the default (no secret) path never fails to schedule.
