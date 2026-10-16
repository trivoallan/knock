# Tasks

## 1. Policy

- [ ] 1.1 Add `remediate:` to `Defaults`, `ImportProfile` and `Variant`, resolved like `transform:`; verify with resolution tests
- [ ] 1.2 Per-list vocabulary and the widened mirror rule; verify with the validation scenarios
- [ ] 1.3 `upgradePackages` without `epoch`, with a message naming the order; verify with a test loading the former shape
- [ ] 1.4 Refuse `remediate:` on non-rebuildable artifact types; verify with a test
- [ ] 1.5 Regenerate the published schema and `docs/reference/`; verify with `make lint`

## 2. Plan, apply, staging

- [ ] 2.1 `remediate: {epoch}` (outside the key, epoch validated on load) and `remediated` on `PlannedOperation`; verify with key and unsafe-epoch tests
- [ ] 2.2 Build transform then remediation for an operation carrying an order, copy-only included; withhold `remediation-undeclared`; verify with the spec scenarios
- [ ] 2.3 Record the remediation in the stamp and the predicate without touching the transform version; verify that an unchanged next pass plans nothing, copy-only included
- [ ] 2.4 `stages()` on the order, epoch on `StagedEntry`, withhold `remediation-unstaged` without `--stage-to`; verify that a transform-only rebuild is placed directly and an unstaged order is never pushed
- [ ] 2.5 `AppliedOperations` (`--applied-out`) with its published schema; verify the source → placed link and the withheld reasons

## 3. Regression contract

- [ ] 3.1 A copy is placed without staging, a plan without orders applies unchanged, `--plan-out` never writes an order; verify with `make test`
- [ ] 3.2 Rewrite `test_only_an_operation_that_builds_is_staged` as "only a remediation is staged"; verify with `make test`

## 4. Docs

- [ ] 4.1 Revise ADR 0054, update `docs/examples/` and `TODOS.md` (`verify --require repaired-since` reads `remediation.epoch`; kind demo under `remediate:`); verify with `make lint`
