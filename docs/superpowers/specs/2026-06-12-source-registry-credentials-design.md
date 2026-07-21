# Source-registry credentials — authenticate pulls to dodge rate limits

**Status:** approved (design)
**Date:** 2026-06-12
**Related:** [`2026-06-12-local-transform-demo-design.md`](2026-06-12-local-transform-demo-design.md) (the demo whose `make demo-transform` hit the limit).

## Problem

knock pulls each policy's **source** image anonymously, so high-volume demos and real deployments hit Docker Hub's **unauthenticated pull rate limit (429)** — exactly what blocked the `local-transform` e2e (`buildctl` pulling `debian` returned `toomanyrequests`). The credential model already exists for **destinations** (`RegistryConfig` in `knock/config.py` carries `username`/`password`, and `reconcile` runs `regctl registry login` for each destination host), but the **source registry is never authenticated**.

## Finding (what makes this nearly code-free)

Both source-pulling clients read the **standard Docker `config.json`**:

- `buildctl` (rebuild path) forwards credentials from `$DOCKER_CONFIG/config.json` to buildkitd natively.
- `regctl` (copy path) reads Docker's `config.json` as a credential fallback — its own `registry login` help says *"This may not be necessary if you have already logged in with docker."*

And knock's **destination** logins do **not** collide with a Docker config: `regctl registry set`/`login` persist to regctl's own config, not Docker's. Verified empirically (knock image, `regctl v0.11.5`):

```
DOCKER_CONFIG=/tmp/dockercfg  REGCTL_CONFIG=/tmp/regctlcfg/config.json  regctl registry set localhost:5000 --tls disabled
→ /tmp/regctlcfg/config.json gains the host; /tmp/dockercfg/config.json stays {"auths":{}}
```

So a **read-only Docker `config.json` mounted for source creds** is read by both clients, while destination logins keep writing to a separate, writable `REGCTL_CONFIG`.

## Goal

Let an operator authenticate source pulls by supplying a standard Docker `config.json`, **opt-in**, wired once in `deploy/base` so **every tier** (lite / transform / full / prod) benefits. Absent the secret, behaviour is unchanged (anonymous). **No knock code change**, no policy/example change.

## Design

### `deploy/base/cronjob-reconcile.yaml` — the `knock` container

- **env**
  - `DOCKER_CONFIG=/docker-config` — where `buildctl` and `regctl` look for source creds.
  - `REGCTL_CONFIG=/tmp/.regctl/config.json` — pin regctl's *own* config (destination `registry set`/`login`) to the writable `work` mount, so it never tries to write the read-only Docker config. (This is already regctl's default under `HOME=/tmp`; setting it explicitly makes the separation deterministic regardless of `DOCKER_CONFIG`.)
- **volumeMounts**: `/docker-config` (`readOnly: true`).
- **volumes**: a secret volume from `knock-docker-config`, **`optional: true`**, projecting key `config.json`.

Opt-in semantics: with the secret absent, the optional volume mounts empty → `/docker-config/config.json` does not exist → both clients fall back to anonymous (today's behaviour). With the secret present, both authenticate. `readOnlyRootFilesystem: true` is preserved — the Docker config is a read-only mount, and regctl writes only under `/tmp` via `REGCTL_CONFIG`.

Only the reconcile container is touched: it is the sole component that pulls the **source** (docker.io). The blast-radius Job reads the **destination** registry only, so it is left unchanged.

### The secret

A generic (`Opaque`) secret named `knock-docker-config` with a single key **`config.json`** holding a standard Docker config (`{"auths": {"https://index.docker.io/v1/": {"auth": "<base64 user:pass>"}}}`). A `kubernetes.io/dockerconfigjson`-typed secret is deliberately *not* used: its key is `.dockerconfigjson`, which would not land as `config.json` inside `$DOCKER_CONFIG` without an extra `items` remap.

### Makefile affordance — `make docker-auth`

A one-command way to seed the secret from a Docker Hub username + access token, building an **inline-auth** `config.json`:

```make
docker-auth: ## Seed source-registry creds (set DOCKER_USER + DOCKER_PASS) so pulls authenticate (avoids rate limits)
	@test -n "$$DOCKER_USER" && test -n "$$DOCKER_PASS" || \
	  { echo "ERROR: set DOCKER_USER and DOCKER_PASS (a Docker Hub username + access token)"; exit 1; }
	@printf '{"auths":{"https://index.docker.io/v1/":{"auth":"%s"}}}' \
	  "$$(printf '%s:%s' "$$DOCKER_USER" "$$DOCKER_PASS" | base64 | tr -d '\n')" \
	  | $(KUBECTL) -n $(NS) create secret generic knock-docker-config \
	      --from-file=config.json=/dev/stdin --dry-run=client -o yaml | $(KUBECTL) apply -f -
```

`DOCKER_USER=<user> DOCKER_PASS=<token> make docker-auth && make demo-transform` then pulls `debian` authenticated. Idempotent (apply-from-dry-run).

**Why not copy `~/.docker/config.json`?** Verification surfaced that under Docker Desktop (macOS/Windows) that file carries only a `credsStore` keychain reference, **no inline `auth`** — so a copied config authenticates nothing in-cluster. Building the config from explicit `DOCKER_USER`/`DOCKER_PASS` is portable across all hosts/CI. (An access token, not the account password, is the right `DOCKER_PASS`.)

### Docs

- `deploy/overlays/local-transform/README.md`: a note that if you hit Docker Hub rate limits, `make docker-auth` (or creating the `knock-docker-config` secret) authenticates source pulls. (`local-lite` has no README; its walkthrough lives in `docs/examples/README.md`.)
- `docs/examples/README.md`: a short note in the rate-limit-prone walkthrough.

## Non-goals

- No knock application code, no port/adapter change.
- No change to the destination-auth roster (`KNOCK_REGISTRIES`) or its `regctl login` flow.
- No new policy/example (this is deployment config, not a `MirrorPolicy` feature).
- Not modelling source creds inside `KNOCK_REGISTRIES` — the standard Docker config is the credential surface (the operator's choice in design review).

## Architecture sync

- **C4 unchanged, deliberately.** Docker Hub (the source registry) is already an external system in the model and knock already pulls from it; adding authentication is an integration detail, not a new actor/system/integration at context or landscape level. `workspace.dsl` does not drift. (Noted to satisfy the "spec that shifts architecture updates C4" gate — this spec does not shift it.)
- **No examples drift**: the change is deployment wiring, not a user-facing policy feature, so `docs/examples/` policies are untouched (only a rate-limit note is added).

## Testing & verification

No application code, so verification is operational. All of the following were **proven in kind** during implementation:

1. **regctl write-target**: with `DOCKER_CONFIG` set read-only and `REGCTL_CONFIG` set, regctl's destination `registry set` writes to `REGCTL_CONFIG` and leaves the Docker config untouched.
2. **Kustomize** — `local-lite`, `local-transform`, `local-full` all render with the reconcile container carrying `DOCKER_CONFIG`/`REGCTL_CONFIG` env and the optional `knock-docker-config` mount; `BUILDKIT_HOST` still composes (env strategic-merge).
3. **Opt-in absent** — with no secret, the reconcile pod reaches `Running` (the `optional: true` volume mounts empty, no `FailedMount`); pulls stay anonymous.
4. **Opt-in present — creds are consumed by buildkit (proven)**: seeding `knock-docker-config` with a (bogus) inline auth changed the source-pull error from `429 Too Many Requests` (anonymous) to **`401 unauthorized`** — buildkit read the mounted `config.json` and authenticated. With *valid* `DOCKER_USER`/`DOCKER_PASS` the pull succeeds and bypasses the anonymous rate limit; `make docker-auth` correctly emits `config.json = {"auths":{"https://index.docker.io/v1/":{"auth":"<base64 user:pass>"}}}`.

## Risks

- **Docker config format** — must be a valid Docker `config.json` with an `auths` entry for `https://index.docker.io/v1/`. `make docker-auth` builds it from `DOCKER_USER`/`DOCKER_PASS`, sidestepping hand-authoring and the non-portable Docker Desktop `credsStore` case (where `~/.docker/config.json` holds no inline auth).
- **Stale/expired creds** — an invalid token makes pulls fail with `401 unauthorized` rather than the anonymous `429`; documented in the rate-limit note. `DOCKER_PASS` should be a Docker Hub access token, not the account password.
- **`optional: true` reliance** — the base must keep the secret volume optional so the default (no secret) path never fails to schedule.
