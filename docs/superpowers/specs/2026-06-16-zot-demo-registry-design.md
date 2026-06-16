# Zot as the demo registry (with its built-in UI) + text logs in the deployment Jobs

Date: 2026-06-16

## Context

Two small, related gaps in the reference deployment, both about *seeing what houba did*:

1. **No way to browse the mirror.** The throwaway demo registry is `registry:2`, which has no
   web UI. After a reconcile you can read the blast-radius report, but you cannot *look* at the
   repos/tags houba pushed or the provenance annotations stamped on each manifest. "The label is
   the product" — yet the demo gave no way to see the label.
2. **JSON logs in the demo Jobs.** `deploy/base` set `HOUBA_LOG_FORMAT=json`, so `make logs` /
   `kubectl logs` on the reconcile and blast-radius Jobs emitted machine-formatted JSON. Those
   logs are read by a *person* watching the demo, where JSON is noise. houba's own default is
   `text`; the deployment overrode it the wrong way for its audience.

## Decision

**Registry → Zot.** Replace the throwaway `registry:2` with [Zot](https://zotregistry.dev), an
OCI-native registry that ships a **built-in web UI** (the `search` + `ui` extensions, present in
the full `zot-linux-amd64` image). This solves "a UI for the registry" with **no second
component and no CORS plumbing** — the UI is served by the registry itself on the same port. The
alternative considered (keep `registry:2` and add a `joxit/docker-registry-ui` sidecar proxying
`/v2/`) needs two Deployments and a proxy hop; Zot folds both into one and is closer to a real
deployment's own console (Harbor/Zot).

The swap is **invisible to houba**: Zot keeps the same Service name and port
(`registry.houba.svc.cluster.local:5000`), serves plain HTTP like `registry:2`, and allows
anonymous read+write by default — so the registry roster, the buildkitd plain-HTTP marking
(`buildkitd.toml`), and the copy (regctl) / rebuild (buildctl) paths are untouched. It stays a
throwaway, demo-only destination, applied out-of-band by `make demo` exactly as `registry:2` was;
a real cluster still points at its own registry.

Browse it with `make registry-ui` (port-forward `svc/registry` 8080→5000, open
`http://localhost:8080`). Zot serves the UI at `/` and the registry API at `/v2/` on the one port.

**Logs → text.** Flip `HOUBA_LOG_FORMAT` in `deploy/base` from `json` to `text`, matching houba's
own default, so the demo Jobs log human-readably. The comment records that a real log pipeline
(Loki/ELK) flips it back to `json` for structured ingestion.

## Scope

- `deploy/overlays/local/registry.yaml` — Zot Deployment + config ConfigMap + Service (the single
  source of truth reused by both `make demo`'s out-of-band step and the `local` overlay).
- `deploy/base/kustomization.yaml` — `HOUBA_LOG_FORMAT=text`.
- `Makefile` — `registry-ui` target; demo echo text.
- Docs (runbook, overlay README, architecture README) + the C4 deployment views and their
  committed Mermaid exports.
- **No application code, port, or adapter change.** Manifests, config default, docs, C4 only.
  Historical specs/ADRs that mention `registry:2` are left as the record of their time.

## Consequences

- The demo can now *show the stamp*, not just report it — the UI lists repos/tags and surfaces the
  OCI + `io.houba.*` annotations on each manifest.
- One registry component instead of registry-plus-UI; pinned to a Zot release (`v2.1.17`) for
  reproducibility.
- The `local` overlay and the Argo reference both get the UI for free (shared manifest).
