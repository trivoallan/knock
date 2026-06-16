# 24. Zot as the demo registry (with its built-in UI) + text logs in the deployment Jobs

Date: 2026-06-16

## Status

Accepted. Refines [23. Single Argo reference deployment that is the demo](0023-single-argo-reference-deployment.md):
the out-of-band throwaway registry it leaves to the demo becomes Zot rather than `registry:2`.
The "buildkitd plain-HTTP marking" referenced below was later removed —
[31. Insecure-registry push is driven by the roster's tls_verify](0031-insecure-registry-from-tls-verify.md)
derives it from `tls_verify` instead.

## Context

The reference deployment gave no way to *browse* what houba pushed — `registry:2` has no web UI —
and its Jobs logged JSON (`HOUBA_LOG_FORMAT=json`), which is noise for the human reading
`make logs`. Both gaps are about *seeing what houba did*; "the label is the product", yet the demo
let you see neither the label nor a clean log.

## Decision

- **Registry → Zot.** Swap the throwaway `registry:2` for [Zot](https://zotregistry.dev), an
  OCI-native registry whose full image bundles a **built-in web UI** (`search` + `ui` extensions).
  This delivers "a UI for the registry" with one component and no CORS plumbing — rejecting the
  `joxit/docker-registry-ui` sidecar alternative (two Deployments + a proxy hop). The swap is
  invisible to houba: same Service name/port (`registry:5000`), plain HTTP, anonymous read+write,
  so the roster, the buildkitd plain-HTTP marking, and the regctl/buildctl paths are unchanged. It
  stays demo-only and out-of-band; a real cluster points at its own registry/console. Browse via
  `make registry-ui`.
- **Logs → text.** Flip `HOUBA_LOG_FORMAT` in `deploy/base` from `json` to `text` (houba's own
  default) so the demo Jobs log human-readably; a real log pipeline flips it back to `json`.

## Consequences

- The demo can show the provenance stamp on each manifest, not just report blast-radius — the UI
  lists repos/tags and surfaces the OCI + `io.houba.*` annotations.
- One registry component (pinned `zot v2.1.17`) instead of registry-plus-UI; the `local` overlay
  and the Argo reference both get the UI from the shared manifest.
- No application code, port, or adapter change — manifests, the log-format default, docs, and the
  C4 deployment views (+ Mermaid exports) only.

Full design spec:
[2026-06-16-zot-demo-registry-design.md](../../superpowers/specs/2026-06-16-zot-demo-registry-design.md)
