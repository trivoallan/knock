## 1. Use case

- [x] 1.1 `CoverageReport` gains `apiVersion: knock.io/v1alpha1` / `kind: CoverageReport` (aliased); schema by alias — verify with a unit test on `model_dump(by_alias=True)`
- [x] 1.2 `CoverageOutcome.sbom_formats`: sorted formats found, `[]` when none, `null` when not probed; `sbom == bool(sbom_formats)` — verify with unit tests (both, none, not probed)

## 2. CLI

- [x] 2.1 `knock audit` JSON output serialized by alias; help text documents the JSON output, the compatibility rule and the schema — verify with a CLI test on the emitted JSON (validated against the schema)

## 3. Reference

- [x] 3.1 `scripts/gen_reference.py` publishes `coverage-report`; `make reference` writes `docs/reference/schemas/coverage-report.{schema.json,md}` and refreshes the CLI page — verify files exist
- [x] 3.2 Drift test: committed `coverage-report.schema.json` equals the generated schema — verify `uv run pytest` passes, fails on a stale file

## 4. Checks

- [x] 4.1 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy knock` all green
