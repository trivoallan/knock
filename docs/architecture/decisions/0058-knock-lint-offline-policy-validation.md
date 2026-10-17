# 58. `knock lint` — offline validation of a policy tree

Date: 2026-10-17

## Status

Accepted.

Builds on [1. MirrorPolicy format](0001-mirror-policy-format.md),
[3. Reconcile output contract](0003-reconcile-output-contract.md) and
[14. Coverage audit](0014-coverage-audit.md).

## Context

A MirrorPolicy is validated only when `knock reconcile` or `knock promote` loads a directory. That
load needs the `KNOCK_*` configuration. Its plan phase reads registries, and it stops at the first
invalid file. Transform step names and parameters are checked even later, during planning. A
repository holding thousands of policies has no cheap way to refuse a broken one before merge. The
published JSON Schema covers single-file structure only: it misses the model's semantic validators,
the merge of `defaults` into imports, and collisions between policies.

## Decision

Add a read-only `knock lint <dir>` verb that validates a whole policy tree without network, external
tools or the DI container, and reports every finding in one run:

- **One loading path.** `load_policy_dir` becomes a thin wrapper over a collecting loader, so `lint`
  and `reconcile` cannot disagree on whether a file loads. `reconcile` keeps failing on the first
  invalid file.
- **Three levels.** Per-file model validation; tree-level checks (defaults merge, transform steps
  against the step registry, alias collisions); configuration references, which run only when
  `KNOCK_REGISTRIES` is set and are otherwise recorded as skipped.
- **Alias collisions are judged on what is knowable offline.** The same literal alias (no `{…}`)
  into the same destination repository is an error. Templates into the same repository are a warning.
- **A versioned report.** `LintReport` (`knock.io/v1alpha1`) on stdout under `KNOCK_LOG_FORMAT=json`,
  text otherwise, with a schema derived from the model and published under `docs/reference/schemas/`.
  Exit 0 means no error, 1 means at least one error, 3 means unreadable configuration.

## Consequences

- A policy repository's CI can gate merges with one command and no registry access.
- Collision detection is weaker than `reconcile`'s, which works on rendered aliases: a template and a
  literal that may meet are not flagged, and two registry names for one host are only matched with
  configuration. `reconcile` stays the backstop, before any mutation.
- A rule added to policy loading reaches `lint` and `reconcile` together. A check `lint` makes beyond
  loading (step validation, collisions) has to stay aligned with the plan phase by tests, not by
  shared code.
- The report is a public contract: within `v1alpha1`, changes are additive only.
