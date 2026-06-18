# `make argocd-ui` + distinct UI ports — design

Date: 2026-06-18
Status: Approved (brainstorm)

## Goal

Add a `make argocd-ui` convenience target (port-forward `svc/argocd-server` + print admin creds) for
the demo (Argo) flow, mirroring `dt-ui` / `registry-ui`. And, so the demo's UIs can run
**simultaneously**, give each service a **distinct local port** — today they all bind `:8080` and
collide (only one UI at a time).

## Port scheme

| Service | Target | Local port | URL |
|---|---|---|---|
| Dependency-Track frontend | `dt-ui` | 8080 *(unchanged)* | <http://localhost:8080> |
| DT apiserver | `dt-ui` | 8081 *(unchanged)* | (the frontend calls it) |
| Zot registry | `registry-ui` | **8082** *(was 8080)* | <http://localhost:8082> |
| ArgoCD | `argocd-ui` | **8083** *(new)* | <https://localhost:8083> |

- **DT stays on 8080/8081.** Its frontend calls the apiserver at a configured URL (`:8081`); moving it
  would mean reconfiguring the frontend's API base URL (`deploy/components/dependency-track/`) — not
  worth the risk, so DT keeps its pair.
- **`registry-ui` moves 8080 → 8082.** Zot's UI is self-contained (same-origin, no cross-port
  coupling) → safe to move, zero config, docs-only impact.
- **`argocd-ui` takes 8083**, HTTPS self-signed.

## Design

### `argocd-ui` — new (DEMO (Argo) section, after `argocd:`; added to `.PHONY`)

```make
argocd-ui: ## Open the ArgoCD UI (port-forward svc/argocd-server; prints admin creds)
	@PW=$$($(KUBECTL) -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' 2>/dev/null \
	      | python3 -c 'import base64,sys; sys.stdout.write(base64.b64decode(sys.stdin.read()).decode())'); \
	  test -n "$$PW" || { echo "ERROR: argocd-initial-admin-secret not found — run 'make demo' (or 'make argocd') first"; exit 1; }; \
	  echo ">> ArgoCD UI at https://localhost:8083  (login admin / $$PW — self-signed cert, accept the warning). Ctrl-C to stop."
	$(KUBECTL) -n argocd port-forward svc/argocd-server 8083:443
```

- **Demo-only, namespace `argocd`**; fails fast with a clear message if `argocd-initial-admin-secret`
  is absent (argo-cd not installed / not in the demo flow).
- **HTTPS self-signed** → `https://localhost:8083`, warned in the echo.
- **Password decoded with `python3`, not `base64 -d`** — macOS (BSD) decodes with `-D`, Linux (GNU)
  with `-d`; `python3` (already required repo-wide) sidesteps the portability trap.
- **No browser auto-open** — prints the URL, like `dt-ui` / `registry-ui`.

### `registry-ui` — port change

`port-forward svc/registry 8080:5000` → `8082:5000`; the echo URL `http://localhost:8080` →
`http://localhost:8082`.

### `dt-ui` — unchanged.

## Docs (part of this change)

- **`make demo` tail:** add `@echo ">> Browse the ArgoCD UI with 'make argocd-ui' (admin creds printed)."`
  after the existing closing echoes.
- **`docs/how-to/reference-deployment.md`:** add a `make argocd-ui` line near `make registry-ui`, and
  update the `registry-ui` URL references `localhost:8080` → `localhost:8082` (≈ lines 43 and 60).
- **`deploy/overlays/local/README.md`:** update any `make registry-ui … localhost:8080` reference →
  `8082`.
- **`docs/examples/reference/debian-xz/DEMO.md`:** if it cites `make registry-ui` / `localhost:8080`,
  update the port to `8082`.

## Error handling

The secret-absent guard (`test -n "$$PW" || { … exit 1; }`) is the only explicit failure path; the
port-forwards surface kubectl errors directly (e.g. `argocd-server` not yet ready).

## Testing / verification

No unit test — port-forward convenience targets, like the existing UI targets (none are unit-tested).
Verification: `make -n argocd-ui` parses cleanly; a repo-wide grep confirms no stale
`registry-ui … localhost:8080` reference remains; manual (after `make demo`): all three UIs reachable
at `:8080` / `:8082` / `:8083` **at the same time**, and `argocd-ui` prints `admin / <password>`.

## Out of scope

- Auto-opening a browser (`open` / `xdg-open`).
- Deleting or rotating `argocd-initial-admin-secret` (argo-cd's own concern).
- Moving DT's ports / any DT config change.
- Any non-demo (production) ArgoCD access pattern.
