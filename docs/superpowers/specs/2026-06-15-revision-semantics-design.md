# Freeze `org.opencontainers.image.revision` semantics — design

*Status: design. Roadmap item: **Now → "Firm the public contract"**. Date: 2026-06-15.*

## Why

*The label is the product* — the provenance stamp is houba's public API and must not wobble before
real artifacts depend on it. One OCI key is currently mis-stamped.

OCI defines `org.opencontainers.image.revision` as the *"Source control revision identifier for the
packaged software"* — a VCS commit. houba mirrors upstream images and does **not** know the upstream
software's SCM commit. Today `domain/stamp.py` stamps `.revision = source_digest` (the source manifest
digest). That is semantically wrong (a manifest digest is not a source-control revision) **and**
redundant: `.revision == .base.digest == source_digest`, two OCI keys carrying the identical value.

## The decision

**Propagate the `.revision` the source image declares itself; if it declares none, do not emit the
key.** Never fabricate one from a digest or tag. Source identity is already carried by `base.name`
(the upstream tag) and `base.digest` (the immutable bytes). Uniform across the **copy** and **rebuild**
paths — the packaged software's SCM revision is the upstream's regardless of houba hardening (houba's
own lineage lives in `io.houba.transform.*`).

This removes the current `.revision == .base.digest` redundancy and makes `.revision` mean what OCI
says, or be absent.

## Where the upstream `.revision` is read

An image may declare `org.opencontainers.image.revision` in two places: a **manifest annotation** or a
**config label** (`LABEL org.opencontainers.image.revision=…` — the common case). `RegctlAdapter.inspect`
already fetches *both* the manifest (`manifest get`) and the image config (`image config`), but today
only extracts `created` from the config and discards `config.config.Labels`. So the upstream revision
is reachable with **no extra registry call** — it just needs surfacing.

- `ImageInfo` gains `config_labels: dict[str, str]`, populated from the image config's
  `config.Labels` (`config.get("config", {}).get("Labels")`). A generic, reusable image fact — not a
  one-off `revision` field baked into the port model.
- Upstream-revision resolution: `annotations.get(K) or config_labels.get(K)` where
  `K = "org.opencontainers.image.revision"`. **Precedence: manifest annotation wins** (OCI-canonical,
  closest to the artifact), config label is the fallback. Conflicts are vanishingly rare in practice.

## Plumbing (minimal, within the hexagon)

- `SourceArtifact` (`domain/reconcile.py`) gains `revision: str | None`.
- `to_source_artifact` (`use_cases/reconcile.py`) resolves it from the source `ImageInfo`
  (`annotations` then `config_labels`, per the precedence above).
- `build_stamp_annotations` (`domain/stamp.py`) gains a `source_revision: str | None` keyword param and
  emits `org.opencontainers.image.revision` **only when it is not None** (stays pure). The current
  unconditional `"...revision": source_digest` line is removed.
- `_do_import` (`use_cases/reconcile.py`) passes `source_revision=source[w.src_tag].revision` — same on
  both the copy and rebuild branches (they share the one `build_stamp_annotations` call).

## Out of scope (assumed)

- **Multi-arch child manifests.** The revision is read at the top level (index/manifest annotations +
  image config) as `inspect` exposes it. If an upstream declares `.revision` only on a per-arch child
  manifest, v1 does not descend into children → the key is omitted. Documented limitation.
- **The signed in-toto predicate is unchanged.** It already carries `source` + `source_digest`; adding
  the upstream revision to the signed predicate is a possible follow-up, not this change.
- **`houba audit` / `domain/coverage.is_stamped` is unaffected** — it tests `{prefix}.policy` (or
  `base.digest` when the prefix is empty), never `.revision`.

## Testing (TDD)

- **Domain (`tests/unit/domain`, ≥ 90 %):** `build_stamp_annotations` emits `.revision` iff
  `source_revision` is provided; the key is absent otherwise; `.revision` is no longer forced equal to
  `base.digest`.
- **Use case (fakes):** source declares `.revision` as a manifest annotation → propagated; declares it
  only as a config label → propagated; declares neither → key absent from the stamp; declares both
  (differing) → manifest annotation wins.
- **Adapter (fake-bin regctl):** `inspect` populates `ImageInfo.config_labels` from the image config;
  add a fake-bin scenario whose `image config` output carries a `config.Labels` map.

## Docs to sync (same change)

- ADR mirror under `docs/architecture/decisions/` linking this spec.
- C4 model: **unchanged** — no new port/adapter/actor (extends the existing `ImageInfo` data model on
  `RegistryPort`).
- `docs/examples/`: a shown stamp loses `.revision` when its upstream declares none; refresh the
  walkthrough/expected output accordingly.
- **`CLAUDE.md` gotcha:** the OCI-provenance note lists the stamped keys — update the `.revision`
  description (no longer the source digest; now the propagated upstream revision or absent).
- **Project memory** correction: the `mirrorpolicy-progress` note still says `.revision` maps to the
  *source tag*; it has mapped to the *source digest* since a post-Phase-7 change, and this work changes
  it again to *propagated-or-absent*.
