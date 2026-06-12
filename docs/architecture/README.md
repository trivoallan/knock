# houba — C4 architecture model

[`workspace.dsl`](workspace.dsl) is the [C4 model](https://c4model.com) of houba, written in
[Structurizr DSL](https://docs.structurizr.com/dsl). One model, six views:

- **System Landscape** — houba in its enterprise context, all the way to incident-time
  blast-radius. This carries the product thesis: the provenance *stamp* is read downstream by
  the observability / CMDB stack — houba never calls it, the coupling is the data.
- **System Context** — houba and the systems it integrates with directly (source registries,
  destination registries, BuildKit, and the internal package mirror the hardening rebuild
  pulls from).
- **Container** — houba is a single deployable unit: the `houba` CLI (the reconcile engine; the
  runtime image bundles `regctl` + `buildctl`). This view draws the system boundary around that
  one container and the external systems it drives.
- **Hexagon** — a synthetic overview of the same CLI: the six layers (**cli** → **use cases** →
  **domain**, with **ports** ← **adapters**) as single boxes. The fastest read of the architecture:
  it makes the dependency inversion explicit — use cases *and* adapters both point at the ports —
  and shows the driven adapters reaching the external systems.
- **Component** — the same hexagon fully exploded: every fine-grained component — the thin Typer
  **cli**, the **use cases** (loader + reconcile orchestrator + the `RunReport` contract), the pure
  **domain** (policy schema, planning pipeline, transform engine, provenance stamp), each **port**
  (`typing.Protocol` seam), and each **adapter** wired to its external system.
- **Deployment (Reference / kind)** — the [reference deployment](../superpowers/specs/2026-06-11-reference-deployment-design.md):
  a kind cluster running houba as a Kubernetes CronJob (optionally a sharded Indexed Job for horizontal scale-out, git-sync'd policies, rootless `buildkitd`,
  a `registry:2`/Harbor destination) through to a blast-radius consumer Job. The *same* manifests
  double as the production blueprint — which is why this view maps the deployment 1:1.

This model is the **source of truth** for the context and landscape levels (kept in sync with the
specs — see the [maintenance contract](#maintenance-contract)). The Container, Hexagon, and
Component views document houba's internal structure **as built**; keep them in step with the code when the
layering, ports, or adapters change.

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

Export both views as committable Mermaid (renders natively on GitHub) or PlantUML:

```sh
docker run --rm -v "$(git rev-parse --show-toplevel)/docs/architecture:/work" \
  structurizr/structurizr export \
  -workspace /work/workspace.dsl -format mermaid -output /work/_export
```

Supported `-format` values include `mermaid`, `plantuml/c4plantuml`, `dot`, and `json`.

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
