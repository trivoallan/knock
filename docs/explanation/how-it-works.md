# How knock works

What happens when `knock reconcile` runs, and how the code is laid out. Moved from the README.

## How it works

For each image you bring in, you declare a small `MirrorPolicy` (source, tag-selection rules,
optional hardening steps). `knock reconcile` then, per policy:

1. Lists tags on the source registry (via `regctl`).
2. Selects which tags to import — regex include/exclude filters, semver ordering, moving-tag
   aliases, and a 7-day stability window for moving digests.
3. For each tag: **mirrors** it as-is (`regctl copy`), or — when the policy declares a `transform`
   — **rebuilds** it through BuildKit (`buildctl`) with your hardening steps (internal CAs,
   internal package mirrors, timezone, …).
4. **Stamps** the result with standardized provenance — OCI-standard annotations plus an
   `io.knock.*` transformation lineage, and (when configured) a signed SLSA / in-toto attestation.
5. Pushes to your registry, updates the moving-tag aliases, and archives superseded tags.
6. Reports the run — a human/JSON report to stdout, a structured event journal to stderr — and
   exits with a code reflecting the worst policy outcome.

Change detection is provenance-based and idempotent: re-running `reconcile` is a no-op unless the
source digest moved (past the stability window) or you changed the hardening.

`reconcile` also enforces **retention**: when a policy (or the fleet-wide `KNOCK_RETENTION`) sets
`archive: {keep, olderThanDays}`, knock keeps the N most-recently-imported tags of each stream and
attaches a `pending-deletion` mark (reason `retention-excess`) to the older surplus — reaching the
*valid, in-selection* tags that selection filtering structurally never would. Retention only ever
**marks** (it never hard-deletes, even under `deletionMode: purge`), so removal always passes through
the usage-gated reaper below.

Beyond `reconcile`, the CLI offers:

- **`knock audit`** — a coverage-gap report: walk the registry and list images that do **not** carry
  knock's stamp (`--fail-on-uncovered` makes it a CI gate); `--signed` adds a *signed*-vs-merely-stamped
  tier (`--fail-on-unsigned`), and `--sbom` a *has-SBOM*-vs-merely-stamped tier (observational). This
  is what makes the front door *verifiable* and *trustworthy*.
- **`knock lint <policies-dir>`** — validate a policy tree offline and report every problem at once:
  each file against the model (N1), the tree as a whole — steps, destination ownership, alias
  overlaps (N2) — and, when `KNOCK_REGISTRIES` is set, references to the configuration (N3). It
  calls nothing and changes nothing; `reconcile` stays the backstop for what it cannot see. See
  [Lint a policy repository in CI](../how-to/lint-policies-in-ci.md).
- **`knock purge`** — the reference reaper: hard-delete tags marked `pending-deletion` (by either
  the selection axis or retention) that a usage oracle confirms are unused (gated by
  `KNOCK_PURGE_MIN_IDLE_DAYS`; dry-run unless `--apply`).
- **`knock attach <ref> --report <file>`** — ingest an upstream scan report (e.g. SARIF) and attach
  it as a stamped OCI referrer on the image — additionally **signed** as an in-toto scan attestation
  when `KNOCK_ATTEST_SIGNER` is set, turning "this image was scanned" into a verifiable fact.
  `--fail-on <severity>` doubles it as a CI gate.
- **`knock gc`** — garbage-collect superseded scan-result referrers: keep the newest per
  `(tool, format)` and collect the rest (`--keep` / `--older-than-days`; dry-run unless `--apply`),
  so `attach` volume doesn't pile up over time.

See the [roadmap](../roadmap.md) for what is built versus planned, and the
[design overview](../architecture/design.md) for the architecture.

### Run it as a deployment

A **reference deployment** runs knock as a Kubernetes CronJob (git-sync'd policies, rootless
buildkitd, a blast-radius consumer) — the same `deploy/` manifests serve a local kind demo and a
production blueprint. Fastest taste:

```bash
make demo             # kind up, sync the Argo reference, reconcile the example, print blast radius
```

See [docs/how-to/reference-deployment.md](../how-to/reference-deployment.md).

## Architecture

`knock` follows hexagonal architecture (ports & adapters):

```
knock/
├── domain/      pure logic — mirror_policy, selection, aliases, semver, expand, policy_merge,
│                variants, platforms, reconcile, gate, collision, sharding, stamp, attestation, sbom,
│                coverage, verify, lifecycle, retention, purge, deletion_mode, packaging, scan/,
│                scan_queue, transforms/
├── ports/       typing.Protocol interfaces — registry, image_builder, attestor, sbom, queue,
│                usage_oracle, reporter, clock, source, archiver
├── adapters/    concrete I/O and external formats — regctl_cli, buildkit_cli, cosign_cli,
│                syft_cli, command_usage, redis_streams, structlog_reporter, system_clock,
│                marketplace_json, zip_writer, tree_walker, local_archiver, git_cli
├── use_cases/   orchestration — loader, reconcile, policy_planner, reconcile_registry,
│                reconcile_git, promote, purge, attach, audit, gc, verify, lint,
│                scan_worker, registry_session, report, intake
└── cli/         Typer entry points — reconcile, promote, purge, attach, audit, gc, verify,
                 lint, scan, version
```

**Golden rules**

- `domain/` never imports I/O (no `httpx`, no `subprocess`, no `os.environ`, no clock).
- `use_cases/` receive ports by injection; they never import adapters.
- `cli/` parses arguments and maps exceptions to exit codes; everything else is delegated.
- Environment variables are read only inside `knock/config.py`.

The current adapters all shell out via `subprocess` (`regctl`, `buildctl`) or use the stdlib —
there is no HTTP client. This keeps the business logic 100 % unit-testable with in-memory fakes
(`tests/fakes/*`), and the adapters integration-testable in isolation with fake-bin shell scripts.
The full picture — and the C4 model — is in [`docs/architecture/`](../architecture/design.md).
