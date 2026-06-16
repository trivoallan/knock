# 31. Insecure-registry push is driven by the roster's tls_verify on both paths

Date: 2026-06-16

## Status

Accepted. Refines [24. Zot as the demo registry](0024-zot-demo-registry.md) and
[23. Single Argo reference deployment](0023-single-argo-reference-deployment.md): removes the
overlay-local buildkitd plain-HTTP config they relied on.

## Context

A destination registry's `tls_verify=false` (plain HTTP) was honored by the copy path
(regctl `--tls disabled`) but ignored by the rebuild path: `BuildkitAdapter` emitted
`--output=type=image,…,push=true` with no insecure flag, so buildkitd defaulted to HTTPS and
the push failed with `http: server gave HTTP response to HTTPS client`.

The local overlay worked around this with daemon config — a `buildkitd.toml` marking the
registry `http = true`, mounted by a patch and pointed at with `--config`. But that config
lived **only** in `overlays/local/`; the Argo reference's buildkitd app ships the generic
`components/buildkitd` without it, so the reference deployment's rebuild push failed. Two
mechanisms encoded one fact (is this registry HTTP?), and they had already drifted.

## Decision

Drive BuildKit's insecure push from the **same** primitive regctl already uses — the roster's
`RegistryConfig.tls_verify`. `BuildRequest` carries `tls_verify`; when false the adapter
appends `registry.insecure=true` to the `--output`. One source of truth across the copy and
rebuild paths.

Remove the now-redundant overlay-local daemon config: `buildkitd.toml`,
`patch-buildkitd-insecure.yaml`, the `buildkitd-config` configMapGenerator, and the `--config`
arg patch. Both deployments now use the generic `components/buildkitd` unchanged.

`registry.insecure` covers the **push**; base images are pulled from upstream over HTTPS. A
deployment that must also *pull* base images from a plain-HTTP registry would reintroduce
daemon config — out of scope (no such case today).

## Consequences

- The Argo reference deployment's rebuild push works without per-overlay buildkitd config —
  the drift that broke it is gone.
- One fewer config mechanism: insecure-registry behaviour is configuration of the generic
  `tls_verify` primitive, not a hardcoded daemon file (the no-hardcoding rule).
- Touches code + tests (`BuildRequest.tls_verify`, `BuildkitAdapter`, `reconcile`'s
  `_build_variant`), the `local` overlay manifests, the C4 DeployLocal view, and the overlay
  docs. No new spec — this is a refinement of the mechanism in 0023/0024.
