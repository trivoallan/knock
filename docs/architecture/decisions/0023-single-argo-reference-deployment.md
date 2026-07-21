# 23. Single Argo reference deployment that is the demo

Date: 2026-06-15

## Status

Accepted. Supersedes [8. local-transform demo tier](0008-local-transform-demo.md) and
[22. ArgoCD reference deployment (App-of-Apps variant)](0022-argocd-reference-deployment.md):
the App-of-Apps is no longer a *variant alongside* the overlays — it is the single reference,
and the three-tier local overlays collapse to one.

## Context

The deploy/demo surface had grown to six overlapping entry points — three local overlays
(`local-lite` copy, `local-full` rebuild+Harbor, `local-transform` rebuild), a standalone
`prod` overlay, an Argo `demo` app set, and an Argo `prod` app set — driven by ~22 Makefile
targets. `make argocd-prod` on kind was already nearly the whole demo: the same App-of-Apps as
production, with throwaway credentials. The rest was redundancy that drifts. The product thesis
(knock is a stamper, not a mirror) was also undersold: the blessed demo (`busybox`) exercised
only the copy path.

## Decision

Collapse to two artifacts:

- **`deploy/argocd/`** — one App-of-Apps that is both the production reference and the kind
  demo (`make demo`). No demo/prod split, no `ARGOCD_ENV`. The default operators are the
  thesis-minimum: ESO + OpenBao (the secret path, wave 0) + buildkitd (rebuild, wave 1). The
  reference policy (`docs/examples/reference`) demonstrates the copy path (busybox) and the
  rebuild/stamp path (debian `setTimezone`) in one reconcile; the blast-radius consumer reports
  both. The `registry:2` is applied out-of-band.
- **`deploy/overlays/local`** — a single `kubectl apply -k` overlay as the inner-loop escape
  hatch (`make local`), covering the App-of-Apps' git-sync gap for uncommitted manifests.

KEDA + Prometheus (autoscaling + its metrics source) leave the default path and remain on disk
as the optional `components/keda-buildkitd` add-on, documented in the runbook. Harbor-backed
hardening (`injectCA` + `rewritePackageSources`) stays a standalone feature example, not part of
the self-contained demo.

## Consequences

- One blueprint, one demo — the demo *is* the production reference, eliminating drift between
  them and cutting the Makefile from ~22 targets to ~13.
- The local overlay reflects uncommitted manifests; the Argo reference reads children from git
  (push-to-iterate), which is why the escape hatch is retained.
- The reference policy lives in per-policy subdirectories (`reference/busybox`,
  `reference/debian-tz`) so `POLICY_DIR=docs/examples/reference` reconciles both for the demo,
  while a copy-only run (the README walkthrough, the CI smoke) can target `reference/busybox`
  alone without a BuildKit daemon.
- No product feature is removed — only redundant demo wiring. The non-reference examples
  (`hardened`, `attested`, `retention`, `scan`, `pending-deletion`, `redis`) remain as feature
  documentation. No application code, port, or adapter changes — manifests, Makefile, CI, docs,
  and the C4 model only.
- The C4 model collapses its seven per-example/prod/argocd deployment views to two
  (`DeployReference`, `DeployLocal`).

Full design spec:
[2026-06-15-single-argo-reference-deployment-design.md](../../superpowers/specs/2026-06-15-single-argo-reference-deployment-design.md)
