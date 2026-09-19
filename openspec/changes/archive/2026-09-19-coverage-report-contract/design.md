## Context

`CoverageReport` (`knock/use_cases/audit.py`) is a snake_case Pydantic model serialized by
`model_dump_json()` in `knock/cli/audit.py`. `coverage_report_json_schema()` exists but is only
exercised by a unit test. The published schemas (`mirror-policy`, `scan-predicate`,
`reconcile-plan`) are written by `scripts/gen_reference.py` into `docs/reference/schemas/`, and CI
re-runs the generator and fails on diff. `docs/reference/command-line-interface.md` is itself
generated from the Typer app.

## Goals / Non-Goals

**Goals:** a consumer can validate the report, detect its version, and learn which SBOM formats an
image carries, without any existing field changing.

**Non-Goals:** probing the *signed SBOM attestation* per format (the probe stays on SBOM referrers,
as `sbom` does today); renaming the report's snake_case fields to camelCase; a text-output change.

## Decisions

- **`apiVersion` + `kind`, as `ReconcilePlan` does.** Same group and version string
  (`knock.io/v1alpha1`) so knock has one convention for versioned documents. The two fields are
  camelCase via aliases (as in the plan) while existing fields stay snake_case — renaming them would
  break the consumer this change exists for. The CLI and the schema therefore both use `by_alias`.
  Alternative considered: a `schema_version: 1` integer — rejected, it would be a second convention.
- **`sbom_formats` next to `sbom`, not instead of it.** `sbom` is kept for compatibility and defined
  as `bool(sbom_formats)`. Formats are sorted names from `FORMAT_MEDIA_TYPES` so the output is
  deterministic. Every known format is probed (no short-circuit): one more `list_referrers` per
  covered image when the first format is present — acceptable for an opt-in probe.
- **Schema published through the existing generator** (`SCHEMAS` slug `coverage-report`, sidebar
  position 4). The drift guard is twofold: CI's `gen_reference` diff (already there) and a unit test
  comparing the committed `coverage-report.schema.json` to `coverage_report_json_schema()` — the
  unit test runs without the `docs` group, so drift fails `uv run pytest` locally too.
- **CLI doc in the command docstring.** The CLI reference page is generated from Typer, so the JSON
  output is documented in `audit`'s help text rather than by hand-editing the generated page.

## Risks / Trade-offs

- [`v1alpha1` reads as unstable] → the compatibility rule is explicit and applies to it; a later
  `v1` is a version bump under the same rule.
- [Mixed casing in one document] → confined to the two envelope fields; documented in the schema.
