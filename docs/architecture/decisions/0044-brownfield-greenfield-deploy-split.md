# 44. Name the two deployment views as Brownfield (headline) and Greenfield (Reference B, advanced)

Date: 2026-06-26

## Status

Accepted.

Supersedes the informal labels introduced in [4. Reference deployment](0004-reference-deployment.md) and
[8. Local-transform demo](0008-local-transform-demo.md).

## Context

The C4 model carries two deployment views:

- **DeployLocal** — `kubectl apply -k`, plain Zot, no Argo/ESO operators. The original intent was
  "inner-loop escape hatch"; post brownfield-demo reframe it is the primary audience path: any
  team that already runs a cluster can drop houba in without adopting a full GitOps stack.
- **DeployReference** — the Argo App-of-Apps (ESO + OpenBao wave-0, houba + buildkitd wave-1).
  The original title called it "the demo", which made it appear to be the only recommended path.

The brownfield demo reframe (2026-06-26) established that the *simpler* path is the headline —
a team with an existing cluster should see their path first. The full GitOps platform remains
important but is an advanced option (Reference B).

## Decision

Rename the two deployment views in `workspace.dsl` and their Mermaid export titles to make the
audience explicit:

| View key | Old title | New title |
|---|---|---|
| `DeployLocal` | Local — inner-loop overlay (make local) | Brownfield — drop-in to existing intake (make demo-mongobleed / make local) |
| `DeployReference` | Reference — Argo App-of-Apps (the demo) | Greenfield — full GitOps platform (Reference B, advanced) |

The Structurizr view **keys** (`DeployLocal`, `DeployReference`) are unchanged so export
filenames are stable. Only the human-facing title and description text is updated.

## Consequences

- The C4 model now communicates the intended audience for each deployment path without reading the
  deployment node comments.
- The brownfield simple path (no operators) is visually the headline; the full GitOps platform is
  clearly marked as advanced.
- The Mermaid exports (`_export/structurizr-DeployLocal.mmd`, `_export/structurizr-DeployReference.mmd`)
  are hand-synced (title line only); a full structurizr regen will confirm no further drift.
