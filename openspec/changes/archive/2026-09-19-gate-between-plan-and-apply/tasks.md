## 1. Domain

- [x] 1.1 `knock/domain/gate.py`: `PlannedOperation`, `ReconcilePlan` (+ `reconcile_plan_json_schema`), `Gate` (record / filter); unit tests
- [x] 1.2 `VariantReconcile.to_rebuild` (the transform-change subset of `to_update`); unit test

## 2. Use case

- [x] 2.1 `OperationKind` / `Counts` gain `withheld`; report arithmetic, text and structured log totals (text shows it only when non-zero)
- [x] 2.2 `reconcile_policies(gate=)` → `RegistryPlanner` → `_apply_plan`: record planned operations, withhold unapproved ones, keep aliases off withheld imports
- [x] 2.3 Under the gate, `admit` signs only approved placements; backfill attests without signing
- [x] 2.4 Unit tests: plan-out records and places nothing; update vs rebuild; approved only; drift withholds; refused update untouched; alias not moved; signing

## 3. CLI

- [x] 3.1 `reconcile --plan-out` (implies dry run) / `--apply-plan`; exclusive; invalid plan → `ConfigError`
- [x] 3.2 Integration tests against the regctl fake-bin; `make reference`

## 4. Docs

- [x] 4.1 ADR 0051
- [x] 4.2 `docs/examples/gate/` + `docs/reference/examples/gate.md`
- [x] 4.3 Publish the `reconcile-plan` schema under `docs/reference/schemas/`
