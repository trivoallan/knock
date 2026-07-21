# `knock audit` — `digest` on every outcome + an `--sbom` tier — design

*Status: design. Date: 2026-06-17. Branch: `tritri/audit-digest-sbom-tier` (off `main`).*

## Why

These are the two **knock-side asks** surfaced by the Backstage coverage-portal design
(`docs/superpowers/specs/2026-06-17-backstage-coverage-portal-design.md`, ADR 0035 — on another
branch). The portal consumes `knock audit`'s JSON report rather than re-walking the registry, and it
needs two things the report does not yet carry:

1. **`digest` on every outcome** — the portal joins images **by digest** (the tag is mutable; the
   digest is the stable identity that survives Harbor's byte-for-byte fan-out). Today
   `CoverageOutcome` is keyed only by `image_ref` (`host/repo:tag`).
2. **An `--sbom` tier** — the portal's "queryable here" bar = *is a package SBOM present for this
   image?* Since [unify-SBOM-on-syft](2026-06-17-sbom-copy-path-unify-syft-design.md) (#140) the SBOM
   is attached as an OCI referrer on both paths, so it is probeable exactly like the cosign signature
   that `--signed` already probes.

Scope is deliberately small and **observational** — no new CI gate (YAGNI; `--fail-on-no-sbom` is a
trivial follow-on if a use emerges). `audit_exit_code` is unchanged.

## 1. Domain — none

The SBOM media types already live in `domain/sbom.py` (#140): `FORMAT_MEDIA_TYPES = {"spdx-json":
"application/spdx+json", "cyclonedx-json": "application/vnd.cyclonedx+json"}`. The probe reuses them so
it stays in sync with what knock attaches. No new domain code.

## 2. Port + adapter — surface the digest from the existing annotation read (approach A)

The audit sweep uses `RegistryPort.get_annotations(ref) -> dict` — the deliberately *light* path
("no digest/config fetch", unlike `inspect()` which also pulls the config blob). We want the digest
**without** that config fetch and **without** a second round-trip, so:

- **`RegistryPort.get_annotations` returns `(digest, annotations)`** instead of just `annotations`.
  The digest is the descriptor digest regctl already resolves in the same `manifest get` — one call,
  no config blob. (`inspect()` is left as-is for reconcile; rejected here for its config fetch across
  a whole-registry sweep.)
- **`RegctlAdapter.get_annotations`** returns the resolved manifest digest alongside the annotations
  (from the same `manifest get`).
- **`FakeRegistryPort.get_annotations`** returns a seeded digest + annotations (the fake gains a
  per-ref digest seed).

`get_annotations` has exactly **one caller** — `use_cases/audit._classify` — so the signature change
is contained. (Verified: `reconcile`/`attach` use `inspect`/`annotate`, not `get_annotations`.)

## 3. Use case — `use_cases/audit.py`

- `CoverageOutcome` gains:
  - `digest: str | None = None` — the join key; populated for **every** resolvable image (covered
    *and* uncovered), `None` only on a read error.
  - `sbom: bool | None = None` — `None` = not probed; set only on **covered** images when
    `check_sbom` (mirrors `signed`).
- `CoverageCounts` gains `with_sbom: int = 0` / `without_sbom: int = 0` (mirror of `signed`/`unsigned`).
- `_classify(image_ref, *, registry, label_prefix, check_signed, check_sbom)`:
  - `digest, annotations = registry.get_annotations(image_ref)`; carry `digest` into the outcome.
  - after `covered`, if `check_sbom`: `sbom = any(registry.list_referrers(image_ref, mt) for mt in
    FORMAT_MEDIA_TYPES.values())` (probe **only covered**, like `--signed`).
- `audit_coverage(..., check_sbom: bool = False)` threads the flag and tallies `with_sbom` /
  `without_sbom` (`sum(1 for o in outcomes if o.sbom is True / is False)`).
- **`audit_exit_code` is unchanged** — no `--fail-on-no-sbom` (YAGNI).

## 4. CLI — `cli/audit.py`

- Add `--sbom` (`typer.Option`, help: "Also probe each stamped image for a package SBOM referrer.")
  — the twin of `--signed`. Threads `check_sbom` into `audit_coverage` and `_render`.
- No new gate flag; exit-code path untouched.

## 5. Edges / scope (assumed)

- **`--sbom` probes only covered images** — an uncovered image never carries an knock SBOM, so `sbom`
  stays `None` there (same shape as `signed`).
- **Either SBOM format counts** — `with_sbom` is true if *any* known SBOM media type has a referrer
  (a policy may emit spdx-json, cyclonedx-json, or both via `KNOCK_SBOM_FORMATS`).
- **`digest` on uncovered images too** — the portal joins dark images by digest as well, so it is not
  gated on `covered`.
- **No cryptographic verification** — presence of the referrer, same ceiling as `--signed`.

## 6. Testing (TDD, one behavior per commit)

- **Use case (`tests/unit/use_cases/test_audit*.py`):** `digest` populated from the (digest,
  annotations) read on covered and uncovered outcomes, `None` on a read error; `sbom` True when an
  SBOM referrer exists, False when none, `None` when `check_sbom` is off or the image is uncovered;
  `with_sbom`/`without_sbom` counts; `--signed` behavior unchanged.
- **Fake (`tests/fakes/registry.py` + its unit test):** `get_annotations` returns the seeded
  `(digest, annotations)`; existing callers/tests updated for the new return shape.
- **Integration CLI (fake-bin `regctl`):** `audit --sbom` exits 0 and the JSON report carries `sbom`
  per covered image + the digest per image; without `--sbom`, `sbom` is `None`. Mirror the existing
  `--signed` integration test.
- Coverage gates hold (≥ 80 % global, ≥ 90 % `knock.domain` — no domain change).

## 7. Docs to sync (same change)

- `make reference` — the `audit` CLI help gains `--sbom`; regenerate `docs/reference/` and commit.
- ADR mirror under `docs/architecture/decisions/` (next free id on `main`) linking this spec — a thin
  record of "audit report gains `digest` + an `--sbom` referrer tier; observational, no gate".
- C4 `workspace.dsl`: **unchanged** — no new port/adapter/actor; `--sbom` is the twin of the existing
  `--signed`, and the `get_annotations` return-shape change is a refinement of an existing port. (The
  `audit` component description may note the SBOM tier.)
- `docs/how-to/` / `docs/reference/`: note the `--sbom` flag where `--signed` is documented.
- No `docs/examples/` change (no `MirrorPolicy` field touched).
