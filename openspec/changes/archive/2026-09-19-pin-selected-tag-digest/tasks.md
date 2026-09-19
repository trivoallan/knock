## 1. Domain

- [x] 1.1 `TagSelection.pins` with digest validation; a test rejects a malformed digest
- [x] 1.2 `VariantPlan.pins` carried by `expand_import`
- [x] 1.3 `reconcile_variant`: a mismatch is withheld (`pin_mismatch`), a match skips the stability window, an alias targeting a withheld tag is not re-pointed, the tag stays desired

## 2. Report

- [x] 2.1 `OperationKind` / `Counts` gain `pin_mismatch`; `Operation.pinned_digest`
- [x] 2.2 `reconcile_registry` emits one `pin_mismatch` operation per withheld tag; no copy, annotation, signature or deletion
- [x] 2.3 Text recap shows `pin_mismatch=`; the exit code is unchanged

## 3. Docs

- [x] 3.1 `make reference`
- [x] 3.2 `docs/examples/admission/admitted-redis.yml` pins its tag
- [x] 3.3 ADR 0052 mirrors this change
