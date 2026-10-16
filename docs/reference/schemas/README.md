# Published schemas

The machine-readable contracts knock publishes, rendered for humans. Each page has a matching
`.schema.json` for editor and CI validation. `make reference` writes both.

- [MirrorPolicy](mirror-policy.md) ([`mirror-policy.schema.json`](mirror-policy.schema.json))
- [Scan attestation predicate (/scan/v1)](scan-predicate.md) ([`scan-predicate.schema.json`](scan-predicate.schema.json))
- [ReconcilePlan (the gate's plan file)](reconcile-plan.md) ([`reconcile-plan.schema.json`](reconcile-plan.schema.json))
- [StagedRebuilds (the remediated images held in staging)](staged-rebuilds.md) ([`staged-rebuilds.schema.json`](staged-rebuilds.schema.json))
- [AppliedOperations (what --apply-plan did with each operation)](applied-operations.md) ([`applied-operations.schema.json`](applied-operations.schema.json))
- [CoverageReport (knock audit JSON output)](coverage-report.md) ([`coverage-report.schema.json`](coverage-report.schema.json))
