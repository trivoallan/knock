# houba — C4 architecture model

[`workspace.dsl`](workspace.dsl) is the [C4 model](https://c4model.com) of houba, written in
[Structurizr DSL](https://docs.structurizr.com/dsl). One model, five structural views plus one
deployment view per worked example (and the production blueprint):

- **[System Landscape](_export/structurizr-Landscape.mmd)** — houba in its enterprise context, all
  the way to incident-time blast-radius. This carries the product thesis: the provenance *stamp* is
  read downstream by the observability / CMDB stack — houba never calls it, the coupling is the data.
- **[System Context](_export/structurizr-Context.mmd)** — houba and the systems it integrates with
  directly (source registries, destination registries, BuildKit, and the internal package mirror
  the hardening rebuild pulls from).
- **[Container](_export/structurizr-Container.mmd)** — houba is a single deployable unit: the
  `houba` CLI (the reconcile engine; the runtime image bundles `regctl` + `buildctl`). This view
  draws the system boundary around that one container and the external systems it drives.
- **[Hexagon](_export/structurizr-Hexagon.mmd)** — a synthetic overview of the same CLI: the six
  layers (**cli** → **use cases** → **domain**, with **ports** ← **adapters**) as single boxes. The
  fastest read of the architecture: it makes the dependency inversion explicit — use cases *and*
  adapters both point at the ports — and shows the driven adapters reaching the external systems.
- **[Component](_export/structurizr-Component.mmd)** — the same hexagon fully exploded: every
  fine-grained component — the thin Typer **cli**, the **use cases** (loader + reconcile
  orchestrator + the `RunReport` contract), the pure **domain** (policy schema, planning pipeline,
  transform engine, provenance stamp), each **port** (`typing.Protocol` seam), and each **adapter**
  wired to its external system.
- **Deployment — the reference (which is the demo), plus the local inner-loop overlay.** The
  [reference deployment](../superpowers/specs/2026-06-15-single-argo-reference-deployment-design.md)
  collapses to two views — the same kustomize base underlies both, so the demo IS the blueprint:
  - **[Reference · Argo App-of-Apps](_export/structurizr-DeployReference.mmd)** — the single
    reference, which on kind is the demo (`make demo`) and adopts unchanged to a real cluster: an
    Argo App-of-Apps brings up ESO + OpenBao (wave 0) then houba + `buildkitd` (wave 1), reconciles
    the reference policy (busybox copy + debian rebuild) git-sync'd from the policy repo, pushes to
    a throwaway Zot (registry + built-in UI) applied out-of-band, and uploads each rebuilt image's
    SBOM to an off-the-shelf Dependency-Track — the worked-example currency consumer (ADR 0035).
    KEDA + Prometheus autoscaling is an optional add-on (`components/keda-buildkitd`), deliberately
    off this path.
  - **[Local · inner-loop overlay](_export/structurizr-DeployLocal.mmd)** — the escape hatch
    (`make local`, `kubectl apply -k overlays/local`): `buildkitd` + a throwaway Zot (registry +
    built-in UI), a plain-secret roster, no operators, and the same Dependency-Track glue for the
    SBOM publish loop (ADR 0035). Reconciles the same reference policy and renders local,
    uncommitted manifests.

  (Optionally a sharded Indexed Job swaps in for the CronJob for horizontal scale-out.) These views
  track the [`deploy/`](../../deploy) manifests and the
  [`docs/examples/reference/`](../examples/reference) policy — keep them in step when a manifest or
  the reference policy changes.

This model is the **source of truth** for the context and landscape levels (kept in sync with the
specs — see the [maintenance contract](#maintenance-contract)). The Container, Hexagon, and
Component views document houba's internal structure **as built**; keep them in step with the code when the
layering, ports, or adapters change.

The **Vulnerability scanner** system (a SARIF-emitting tool — CI pipeline, registry-native
scanner, or scan service) is modelled as one external system with **two** relations: it
produces a report houba *ingests* via `houba attach` (scanner → houba), and houba *invokes* a
configured one on the SBOM at admission via the reconcile scanstep gate (houba → scanner,
`subprocess (HOUBA_SCAN_EVALUATOR_CMD)`). houba owns neither the tool nor its CVE database —
the same deployment-supplied, interchangeable shell-out pattern as the usage oracle (see ADR 0039).
The houba→Signing service edge (introduced for the rebuild path in #49) now also covers
`houba attach` signing the scan referrer (`https://houba.dev/predicate/scan/v1`) — no new
model element; the same Signing service and Transparency log systems are reused.

The prose companion to this model — the problem framing, the hexagon, the policy schema, the
reconcile loop, the provenance stamp — lives in [`design.md`](design.md).

## Documentation & decisions

The workspace also embeds two documentation panes (attached to the `houba` software system, so
they render in the interactive viewer):

- **Documentation** — [`design.md`](design.md), via `!docs`.
- **Decisions** — the design specs as ADRs. [`decisions/`](decisions/) holds one **thin ADR per
  spec** (status + date + the decision, with a `## Status` link graph), each linking to the full
  spec under [`docs/superpowers/specs/`](../superpowers/specs/). They use sequential `NNNN-*.md`
  filenames (adr-tools format) because the importer derives each decision's ID from the leading
  number — the dated spec filenames would otherwise all collide on `2026`.

## Render it

### Interactive viewer (Structurizr)

```sh
docker run -it --rm -p 8080:8080 \
  -v "$(git rev-parse --show-toplevel)/docs/architecture:/usr/local/structurizr" \
  structurizr/structurizr local
```

Open <http://localhost:8080>. It loads `workspace.dsl`, live-reloads on change, and lets you
export PNG/SVG from the diagram toolbar. (The old `structurizr/lite` image is deprecated — it now
only prints a banner; `structurizr/structurizr local` is its replacement.)

### Validate & export (Structurizr CLI)

Use the consolidated `structurizr/structurizr` image. (The older `structurizr/cli` image is
deprecated and no longer functional — its entrypoint only prints a migration banner.)

Validate the DSL and run the model inspections — a good CI gate for the maintenance contract
below. Gate on `error,warning`; the one known false-positive (`model.element.noview` on houba,
which is only ever a view *subject*/boundary, never a plain element) is downgraded to `ignore` in
`workspace.dsl`, so the gate exits cleanly:

```sh
docker run --rm -v "$(git rev-parse --show-toplevel)/docs/architecture:/work" \
  structurizr/structurizr validate -workspace /work/workspace.dsl
docker run --rm -v "$(git rev-parse --show-toplevel)/docs/architecture:/work" \
  structurizr/structurizr inspect -workspace /work/workspace.dsl -s error,warning
```

Export every view as committable Mermaid or PlantUML:

```sh
docker run --rm -v "$(git rev-parse --show-toplevel)/docs/architecture:/work" \
  structurizr/structurizr export \
  -workspace /work/workspace.dsl -format mermaid -output /work/_export
```

Supported `-format` values include `mermaid`, `plantuml/c4plantuml`, `dot`, and `json`.

The Mermaid exports are **committed** under [`_export/`](_export) (one `.mmd` per view —
`structurizr-Deploy*.mmd` for the per-example deployment views), so the diagrams are reviewable
without a Structurizr instance — the view list above links straight to them. A raw `.mmd` file
shows as source on GitHub (GitHub only auto-renders Mermaid inside a ```` ```mermaid ```` fence in a
Markdown file); to see it rendered, paste it into [mermaid.live](https://mermaid.live) or any
Mermaid viewer. Re-run the command above after editing `workspace.dsl` to refresh them — the
maintenance contract treats them as generated artifacts that must not drift from the DSL.

## Maintenance contract

Whenever a spec adds or changes an **actor**, an **external system**, or an **integration** —
anything visible at context or landscape level — update `workspace.dsl` **in the same change as
the spec**. A spec under `docs/superpowers/specs/` that shifts the architecture is not complete
until the C4 model reflects it. The model must never drift from the specs.

Likewise, a **new spec** gets a thin ADR in [`decisions/`](decisions/) (next `NNNN-`, status +
date + the decision, linking to the full spec) in the same change — so the Decisions pane stays
complete.

The **Container**, **Hexagon**, and **Component** views track the *code* rather than the specs:
when houba grows a new port/adapter pair, a new domain concern, or a changed layer boundary, update
them in the same change as the code.

The same rule lives in the repository [`CLAUDE.md`](../../CLAUDE.md) so every session sees it.
