# MirrorPolicy format & reconcile contract — Design

**Status:** Draft — pending review
**Date:** 2026-05-22
**Scope:** The declarative `MirrorPolicy` format, the named-registries config model, and the `houba reconcile` command contract. This is the design for Phase C ① (provenance/policy schema) and the entry point of ② (the derive-and-stamp engine).

> Written in English to match the rest of `docs/` and the public-repo convention. The schema field names are the public API.

---

## 1. Context & motivation

houba is a **stamper / single front door** for external OCI artifacts (see [roadmap](../../roadmap.md)): it pulls upstream artifacts, optionally rebuilds images through a hardening policy, and stamps everything with standardized, portable provenance so that — the morning a CVE drops — blast-radius is one query in the org's observability stack.

Today the declaration is a flat `properties.yml` per product ([houba/domain/properties.py](../../../houba/domain/properties.py)): one source, one destination, one tag selection, with SNCF-specific residue (`harbor: blue|orange|both`). This design replaces it with a versioned, identifiable **`MirrorPolicy`** object, and defines how a directory of them is reconciled.

Two product decisions drive the shape:

- **The label is the product.** Because houba's value flows through the stamp into someone else's query tool, the schema is the public API. It must be versioned (`apiVersion`), identifiable (`metadata`), and tool-recognized.
- **Coverage gates value.** houba is meant to be the mandatory path for external artifacts; the format and the reconcile model assume "a directory of policies, converged as a set."

---

## 2. Scope: implemented in v1alpha1 vs forward-compatible-but-deferred

The schema is designed whole; the **implementation is bounded**. The schema admits the deferred items so they need no breaking change later.

| Capability | v1alpha1 | Deferred (schema-ready) |
|---|---|---|
| Envelope (`apiVersion`/`kind`/`metadata`/`spec`) | ✅ | |
| `imports` (selection → destinations), `defaults` + merge | ✅ | |
| `tags`: regex, semverOnly, `names`, `aliases` | ✅ | |
| `variants` (transform-variant + tag suffix) | ✅ | |
| Multi-registry `destinations` | ✅ | |
| `artifactType: image` — full transform vocabulary | ✅ | |
| `artifactType: generic` — copy + stamp, no transform | ✅ | |
| `artifactType: helmChart` — copy + stamp, **chart transform deferred** | ✅ (stamp only) | `rewriteImageRefs`, `setDefaultRegistry`, re-sign |
| Registry `type: harbor` | ✅ | `type: oci` (generic-OCI adapter, needs `RegistryPort`) |
| `reconcile` contract (exit codes, `--dry-run`, partial failure, stateless) | ✅ | |
| Reference deployment manifests (Argo/CronJob/GH Actions) | ❌ | `examples/deploy/` — multi-trigger, never single |

Explicitly **out of scope** (not just deferred — a different product): runtime presence / fleet inventory / an operator. houba stamps; the blast-radius query is assembled in the org's observability stack. End-of-life awareness lives in the sibling tool `regis`.

---

## 3. The `MirrorPolicy` schema

### 3.1 Worked example (everything together)

```yaml
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata:
  name: redis
  labels:
    team: platform-data            # stable key → provenance; human owner resolved downstream
spec:
  artifactType: image              # image | helmChart | generic   (default: image)
  source:
    registry: docker.io            # upstream registry
    repository: library/redis
  defaults:                        # fallback values for every import (rule B merge)
    destinations:
      - { registry: harbor-eu, project: lib, repository: redis }
      - { registry: harbor-us, project: lib, repository: redis }
    transform:
      - injectCA:              { certs: [corp-root-ca] }
      - setTimezone:           { zone: Europe/Paris }
    archive:
      keep: 2
      olderThanDays: 30
    tags:
      semverOnly: true
      excludeRegex: ["-rc", "-alpha"]
  imports:
    - name: v7
      tags:
        includeRegex: "^7\\."      # merges with defaults.tags → semverOnly + excludeRegex inherited
        aliases: ["{major}.{minor}", "latest"]
      # destinations, transform, archive all inherited from defaults
      variants:
        - name: standard           # → redis:7.2  (+ aliases 7.2, latest)
          suffix: ""
        - name: fips               # → redis:7.2-fips  (+ aliases 7.2-fips, latest-fips)
          suffix: "-fips"
          transform:               # replaces defaults.transform (rule B: lists replace)
            - injectCA:   { certs: [corp-root-ca, corp-new-ca] }
            - enableFips: {}
    - name: v6
      tags:
        includeRegex: "^6\\."
        names: ["6.2.14-bookworm"] # explicit, included even if excluded by pattern
        aliases: ["{major}.{minor}"]
      destinations:                # overrides defaults.destinations (list → replace)
        - { registry: harbor-eu, project: lib-legacy, repository: redis }
```

### 3.2 Envelope

- `apiVersion: houba.io/v1alpha1` — schema version. Evolves `v1alpha1 → v1beta1 → v1` with conversion. **Non-negotiable from day one** (the schema is the API).
- `kind: MirrorPolicy` — reserves the kind namespace. A future `kind: TransformProfile` (a reusable, named `transform` list referenced by policies) and `kind: HardeningProfile` are anticipated; the `kind` field makes them additive.
- `metadata.name` — identity, unique within the reconciled set. Used for dedup, selection, and as the stable provenance key.
- `metadata.labels` — free-form; `team` is the conventional stable owner key stamped into provenance.

### 3.3 `spec` top-level

- `artifactType` — discriminator (§6). Default `image`. Gates the `transform` vocabulary.
- `source` — one upstream repository: `{ registry, repository }`. Here `registry` is a **literal upstream hostname** (e.g. `docker.io`, `ghcr.io`) — distinct from `destination.registry`, which references a *named* registry from the roster (§7). **Not** overridable per import (one `MirrorPolicy` = one upstream). Not part of `defaults`.
- `defaults` — fallback values inherited by each import. May hold `destinations`, `transform`, `archive`, `tags`. Optional.
- `imports` — list of import profiles (§4). At least one required.

### 3.4 Merge semantics (rule B) — load-bearing

When an `import` specifies a field also present in `defaults`:

- **Map fields** (`tags`, `archive`): **shallow-merged** key-by-key over the default, one level deep. Example: `defaults.tags = {semverOnly: true, excludeRegex: ["-rc"]}` + `import.tags = {includeRegex: "^7\\."}` → `{includeRegex: "^7\\.", semverOnly: true, excludeRegex: ["-rc"]}`.
- **List fields** (`transform`, `destinations`): **replaced wholesale**. No append/merge.
- Nested lists inside a merged map (e.g. `tags.excludeRegex`) are atomic — replaced if the import specifies them.

Rationale: `transform` is an *ordered* list with dependencies (inject CA before rewriting HTTPS sources that must trust it). Auto-merging ordered lists is ill-defined (the k8s strategic-merge trap). Replace is the only predictable rule; restating a list on override is an explicit, acceptable cost. One level of merge only — no recursion, no list-merge magic.

The same rule applies to a `variant`'s `transform` overriding the import/defaults `transform`.

---

## 4. `imports` — selection → destinations

Each import is one routing profile: a tag selection plus where the results go.

```
import:
  name:         <string, unique within the policy>
  tags:         <TagSelection>          # §5
  destinations: <list<Destination>>     # optional; inherits defaults.destinations
  transform:    <list<TransformStep>>   # optional; inherits defaults.transform
  archive:      <Archive>               # optional; inherits defaults.archive
  variants:     <list<Variant>>         # optional; one implicit "default" variant if absent
```

- **Fan-out** (same tags → N registries) = multiple `destinations`.
- **Routing** (different tags → different destinations) = multiple `imports`.
- A `Destination` = `{ registry: <name>, project, repository }`. `registry` is optional iff exactly one registry is configured; required otherwise. An unknown registry name fails the run fast (§7).

### 4.1 Variants

A variant produces an additional derived artifact from the *same* selected source tag, with a different transform and an output tag suffix.

```
variant:
  name:      <string, unique within the import>
  suffix:    <string>                  # appended to every output tag and alias
  transform: <list<TransformStep>>     # optional; replaces import/defaults transform (rule B)
```

- Output tag = `<concrete-or-alias-tag><suffix>`. Aliases inherit the suffix (`7.2` → `7.2-fips`).
- Absent `variants` ⇒ one implicit variant `{ name: "default", suffix: "" }` using the resolved transform.
- Present `variants` ⇒ the explicit set; include a `suffix: ""` entry if you want the unsuffixed build. No implicit extra.
- All variants of an import go to all of that import's destinations.
- Identity is three-level: `policy.import.variant` — recorded in provenance.

---

## 5. `TagSelection`

```
tags:
  includeRegex: <string|null>          # tags matching are candidates
  excludeRegex: <list<string>>         # matching tags dropped (unless named explicitly)
  semverOnly:   <bool, default true>   # drop non-semver tags; enables {major}/{minor}/{patch}
  names:        <list<string>>         # exact tag names, always included (§5.1)
  aliases:      <list<string>>         # derived moving tags (§5.2)
```

Selected concrete set = `(includeRegex matches − excludeRegex) ∪ names`, then (if `semverOnly`) non-semver tags dropped *except* those in `names`.

### 5.1 Explicit `names`

Exact tag names imported unconditionally — included even if they fail `includeRegex`, match `excludeRegex`, or are non-semver. **Explicit beats pattern.** A name absent upstream → warning + skip, surfaced in the run summary (you cannot import what does not exist).

### 5.2 Automatic aliasing

An **alias** is a moving tag pointing at a concrete derived digest. `aliases` is a list of **templates**; placeholders are resolved per concrete tag:

- `{major}`, `{minor}`, `{patch}` — semver components (require `semverOnly` or a parseable semver tag).
- `{name}` — a named capture group from `includeRegex` (`(?P<name>...)`).
- `latest` — literal keyword; a single group of all selected tags.

Resolution: for each template, render it against every imported concrete tag; group tags by rendered value; for each group, create the alias `= rendered value`, pointing at the **highest** tag in the group (semver descending; lexical fallback). Per variant, the alias gains the variant suffix.

```yaml
# semver ladder (Docker-official style)
aliases: ["{major}", "{major}.{minor}", "latest"]
# 1.36.1 / 1.36.2 / 1.37.0 → 1→1.37.0, 1.36→1.36.2, 1.37→1.37.0, latest→1.37.0

# regex-capture (non-semver)
includeRegex: "^(?P<flavor>debian|alpine)-(?P<ver>\\d+\\.\\d+)$"
aliases: ["{flavor}"]   # debian → highest debian-*, alpine → highest alpine-*
```

Alias rules:

- Aliases are **moving**: re-evaluated every reconcile, re-pointed to the current highest. They are **exempt** from the concrete-tag immutability / 7-day digest-stability window (they are *meant* to move).
- An alias does **not** re-stamp: it points at an already-stamped digest. The `org.opencontainers.image.*` / `io.houba.*` provenance records the *concrete* tag actually imported, never the alias.

---

## 6. Artifact types

`spec.artifactType` discriminates the `transform` vocabulary and the execution path. houba does two separable things; only the first is universal:

1. **Mirror + stamp** — copy the artifact, add provenance annotations. Works for **any** OCI artifact type. The blast-radius thesis applies to charts and every other type ("which Helm charts are hit by this CVE?").
2. **Transform** — rebuild content. Meaningful only for some types; the vocabulary is type-specific.

| `artifactType` | Transform vocabulary | Execution path |
|---|---|---|
| `image` (default) | full — `injectCA`, `rewritePackageSources`, `setTimezone`, `enableFips`, … | rebuild via BuildKit, then push |
| `helmChart` | none in v1alpha1 (deferred: `rewriteImageRefs`, `setDefaultRegistry`, re-sign) | copy + annotate; stamped as `helmChart` |
| `generic` | none — must be empty (validation error otherwise) | copy + annotate |

- `generic` is the **catch-all**: it covers the entire OCI long tail (WASM, SBOMs, signatures, OPA bundles, …) without enumerating them. New named types are added only when they earn a transform vocabulary.
- `artifactType` is recorded in provenance, so blast-radius queries can filter by type.
- The deferred `helmChart` transform `rewriteImageRefs` is high-value: a hardened chart that points at *houba-mirrored* images closes the loop. It is its own design.

### 6.1 Stamping non-image artifacts — implementation note

Stamping an artifact that is *not* rebuilt cannot use plain `skopeo copy` (it cannot add annotations; changing the manifest changes the digest). The copy-and-annotate path is: **pull manifest → add annotations → push** (new digest), via `oras`/`crane`. This is a **second execution path** alongside the image rebuild, and a new adapter concern for the implementation plan. The `image` path bakes annotations during the BuildKit rebuild.

---

## 7. Registries (config)

Multi-registry destinations are the generic replacement for the removed SNCF `blue|orange|both`. Registries are **named** and referenced by name from `destinations[].registry`.

### 7.1 Config model — env-roster

Preserves the 12-factor contract and the rule that `houba/config.py` is the only reader of the environment:

```bash
HOUBA_REGISTRIES=harbor-eu,harbor-us                    # the roster
HOUBA_REGISTRY_HARBOR_EU_URL=https://harbor-eu.example  # name normalized: uppercase, '-' → '_'
HOUBA_REGISTRY_HARBOR_EU_USER=robot$houba
HOUBA_REGISTRY_HARBOR_EU_PASSWORD=...                   # secret per registry, via env
HOUBA_REGISTRY_HARBOR_US_URL=...
HOUBA_REGISTRY_HARBOR_US_USER=...
HOUBA_REGISTRY_HARBOR_US_PASSWORD=...
```

- A custom Pydantic settings source reads the roster and builds a `dict[name → RegistrySettings]`.
- Each registry: `{ url, user, password (SecretStr), type: harbor }`. `type` is forward-compatible; `harbor` is the only value in v1alpha1, `oci` reserved.
- The single-`HOUBA_HARBOR_*` settings are **replaced** by the roster; a single-registry deployment defines exactly one entry.
- An alternative (registries declared in a versioned `registries.yaml`, secrets via env) is rejected: it breaks the env-only invariant and raises secrets-in-files questions.

### 7.2 Composition root

`houba/cli/_di.py` builds a `dict[name → HarborHttpAdapter]`. The reconcile use case resolves the adapter per `destination.registry`. A policy referencing a registry not in the roster → **`ConfigError`, fail fast at reconcile start**, before any mutation.

---

## 8. The `reconcile` command contract

```
houba reconcile <dir> [--dry-run]
```

- **Load & validate first.** All `MirrorPolicy` files under `<dir>` are parsed and validated before any mutation. If *any* file is invalid, abort non-zero — never partial-apply a broken set.
- **Stateless.** Actual state is read from each destination registry at run time. No state store.
- **Partial failure.** Reconcile proceeds policy-by-policy with continue-on-error; per-policy/import/variant/destination status is collected. Exit non-zero if *any* unit failed (so a scheduler/CI sees red), but one failing policy does not block the others.
- **`--dry-run`.** Compute and print the plan (per destination: tags to import/update/delete, aliases to move, variants and transform steps) without mutating. For GitOps PR-preview and CI "plan" stages. Maps to the existing dry-run settings.
- **Idempotent.** Re-running converges to the same state; safe at any cadence.
- **Concurrency.** No internal locking; the scheduler owns non-overlap (e.g. CronJob `concurrencyPolicy: Forbid`).
- **Output.** Structured (structlog JSON) run summary, per unit, ingestible without regex.

The trigger (Argo Workflows, k8s CronJob, GitHub Actions, cron) is a deployment detail, **not** houba's concern. Reference manifests are deferred to a multi-trigger `examples/deploy/` so no single orchestrator becomes a dependency.

---

## 9. Provenance stamp

Universal across artifact types; baked during the image rebuild, or added on the copy-and-annotate path for non-images.

- **OCI-standard annotations** for standard facts: `org.opencontainers.image.source`, `.revision`, `.base.name`, `.base.digest`, `.created`. Any scanner/registry reads them for free.
- **`io.houba.*`** only for the genuinely novel lineage: `io.houba.policy` (= `metadata.name`), `io.houba.import`, `io.houba.variant`, `io.houba.transform.version`, `io.houba.artifact.type`, `io.houba.owner.team` (the stable key from `metadata.labels.team`).
- **Immutable build facts only.** No location fact: the `import.harbor` label is **dropped** — the same digest can live in many registries, so "which registry" is a runtime/location fact resolved downstream, not baked provenance. The human owner is resolved downstream from the stable `team` key, never stamped as a person.

---

## 10. Architecture impact (for the implementation plan)

This design touches, beyond `domain/`:

- **`config.py`** — env-roster custom settings source; `RegistrySettings`; removal of single-`HOUBA_HARBOR_*`.
- **`cli/_di.py`** — `dict[name → adapter]`; per-destination resolution.
- **New domain** — `MirrorPolicy` models (replacing `Properties`), the alias-template resolver, the merge engine, the variant expander, the selection engine extended with `names`.
- **New adapter concern** — a copy-and-annotate path (`oras`/`crane`) for `generic`/`helmChart`, distinct from the BuildKit rebuild.
- **Deferred architecture** — a `RegistryPort` abstraction with `HarborRegistryAdapter` + a future `OciRegistryAdapter` (for registry `type: oci`); the `helmChart` transform vocabulary.

The implementation will decompose into phases at the planning stage: the reconcile engine + schema, multi-registry config, the copy-and-annotate path, the `image` transform vocabulary, then the `helmChart` transform.

---

## 11. Open questions

- **Recursive directory load?** Does `reconcile <dir>` descend into subdirectories, or only the top level? (Lean: recursive, so policies can be organized by team/registry.)
- **`source.registry` credentials.** Pulling from private upstreams may need source-side auth. v1alpha1 assumes public or already-authenticated upstreams; source credentials are a likely near-term addition (same roster mechanism, used for read).
- **Alias collision across imports.** Two imports in one policy could render the same alias (e.g. both produce `latest`). Detection + error vs last-wins — to settle in the plan. (Lean: validation error; aliases must be unique per destination+repository.)
