# Design

The full design, its alternatives and its reviews live in the workspace change
`openspec/changes/split-knock-policy-transform-remediate/design.md` (decisions D1 to D9). This file
keeps only what is specific to knock's code.

## Decisions

- **One validation entry, two vocabularies.** `validate_transform_steps` takes the list's role
  (`transform` or `remediate`) and checks it against that role's allowed names. The mirror rule
  looks at the resolved transform and the earlier remediation steps together.
- **Rendering.** The remediation steps are rendered after the transform steps in the same
  Dockerfile; `upgradePackages` receives the epoch from the order, not from its params. The
  transform version hashes the transform alone.
- **Order lookup.** `Gate.from_plan` keeps a map key → order, so `admits` stays a key check and the
  use case asks the gate for the order of an admitted operation.
- **Staging.** `stages()` takes the order, not `transformed`.
- **Copy-only remediation.** A variant without a transform but with an order is built; its stamp
  writes no transform version (`stamp.py` writes it only for transform steps), so drift stays nil.
- **Withheld reasons.** Reported in `AppliedOperations` and in the run report's withheld count.
