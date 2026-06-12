# houba — C4 architecture model

[`workspace.dsl`](workspace.dsl) is the [C4 model](https://c4model.com) of houba, written in
[Structurizr DSL](https://docs.structurizr.com/dsl). One model, three views:

- **System Landscape** — houba in its enterprise context, all the way to incident-time
  blast-radius. This carries the product thesis: the provenance *stamp* is read downstream by
  the observability / CMDB stack — houba never calls it, the coupling is the data.
- **System Context** — houba and the systems it integrates with directly (source registries,
  destination registries, BuildKit, and the internal package mirror the hardening rebuild
  pulls from).
- **Deployment (Reference / kind)** — the [reference deployment](../superpowers/specs/2026-06-11-reference-deployment-design.md):
  a kind cluster running houba as a Kubernetes CronJob (git-sync'd policies, rootless `buildkitd`,
  a `registry:2`/Harbor destination) through to a blast-radius consumer Job. The *same* manifests
  double as the production blueprint — which is why this view maps the deployment 1:1.

This model is the **source of truth** for the context and landscape levels. It must not drift
from the specs — see the [maintenance contract](#maintenance-contract).

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
below:

```sh
docker run --rm -v "$(git rev-parse --show-toplevel)/docs/architecture:/work" \
  structurizr/structurizr validate -workspace /work/workspace.dsl
docker run --rm -v "$(git rev-parse --show-toplevel)/docs/architecture:/work" \
  structurizr/structurizr inspect -workspace /work/workspace.dsl
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

The same rule lives in the repository [`CLAUDE.md`](../../CLAUDE.md) so every session sees it.
