# 4. Reference deployment (kind)

Date: 2026-06-11

## Status

Accepted

## Context

houba needed a blessed, reproducible topology for running it in an organisation — one
that demonstrates the full loop locally yet doubles as a production blueprint, rather
than diverging demo and prod manifests.

## Decision

Ship one kustomize artifact (base + overlays) that (a) runs the full loop in
[kind](https://kind.sigs.k8s.io) as a Kubernetes CronJob with git-synced policies and a
rootless `buildkitd`, (b) doubles as the production blueprint, and (c) is modelled as a
C4 Deployment view. Cover the loop end-to-end through blast-radius consumption.

## Consequences

The same manifests serve demo and production (anti-drift); a third C4 view is added.
Implemented (`deploy/`, `scripts/blast-radius.sh`, the Deployment view).

Full design spec: [2026-06-11-reference-deployment-design.md](../../superpowers/specs/2026-06-11-reference-deployment-design.md)
