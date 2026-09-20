## 1. Schema: accept `admit` on a git source

- [x] 1.1 Write a failing test asserting a git-sourced policy with `admit: true` parses; run it red
      (`uv run pytest tests/unit/domain/test_mirror_policy.py -k admit -v`)
- [x] 1.2 Remove `_admit_needs_registry_source` from `knock/domain/mirror_policy.py` and widen the
      `admit` `Field(description=...)` to say it covers any placement, image or artifact; verify by
      the test from 1.1 going green and the existing "git source refuses admit" test now failing
- [x] 1.3 Delete the now-obsolete "git source refuses admit" test and verify
      `uv run pytest tests/unit/domain -q` is green
- [x] 1.4 Run `make reference` and commit the regenerated `docs/reference/`; verify the CI drift
      check passes locally (`git diff --exit-code docs/reference/`)

## 2. GitPlanner holds an attestor and refuses admission without one

- [x] 2.1 Write a failing test: `GitPlanner.plan` over a batch containing an `admit: true` policy
      with `attestor=None` raises `ConfigError` (exit code 3 via `exit_code_for`), and places
      nothing; run it red
- [x] 2.2 Add `attestor: AttestorPort | None = None` to `GitPlanner` and the plan-phase guard;
      verify 2.1 goes green
- [x] 2.3 Wire `attestor=attestor` into the `GitPlanner(...)` construction in
      `knock/use_cases/reconcile.py`; verify with a use-case test that a run with a git `admit`
      policy and a configured `FakeAttestorPort` reaches apply instead of raising
- [x] 2.4 Verify a batch of `admit: false` git policies with `attestor=None` still plans and
      applies unchanged (regression test)

## 3. Sign at placement, before the alias moves

- [x] 3.1 Write a failing test: an `admit: true` policy placing a new revision signs
      `{dest_repo}@{manifest_digest}`, and the `FakeAttestorPort.signed` entry is journalled before
      the `FakeRegistryPort.copied` entry that moves the alias; run it red
- [x] 3.2 Sign in `GitPlanner._apply_one` between the `intake_skill` result and the alias
      `registry.copy`; verify 3.1 goes green
- [x] 3.3 Write and green a test that a signing failure fails the operation, leaves the alias
      un-moved, and isolates to the failing policy (the sibling policy in the batch still reports
      success)
- [x] 3.4 Write and green a test that an `admit: false` policy places and stamps the revision and
      makes no signing call
- [x] 3.5 Write and green a test that `--dry-run-tags` with `admit: true` fetches nothing, places
      nothing and signs nothing

## 4. Idempotent backfill on converged artifacts

- [x] 4.1 Write a failing test: an `admit: true` policy whose revision is already placed and whose
      digest has no `COSIGN_ATTESTATION_ARTIFACT_TYPE` referrer signs that digest; run it red
- [x] 4.2 Implement the referrer listing + conditional sign on the already-placed branches of
      `_apply_one` (both the fully converged arrival and the repoint-only arrival); verify 4.1
      green
- [x] 4.3 Write and green a test that a converged, already-signed artifact triggers no signing call
      and no fetch
- [x] 4.4 Write and green a test that a stale alias over a placed-and-signed revision repoints the
      alias and does not sign again
- [x] 4.5 Write and green a test that an `admit: false` policy over converged artifacts lists no
      referrers and signs nothing (the default path pays nothing)

## 5. The gate reads it back

- [x] 5.1 Write and green a use-case test that `knock verify --require image-signature` on a placed
      skill digest passes when the attestor reports a verified image signature, and exits 1 when it
      does not — asserting `verify` needs no image-specific input
- [x] 5.2 Add an integration test driving the real `regctl` against an `ocidir://` layout plus the
      `cosign` fake-bin, asserting the argv `cosign sign` receives names the artifact digest
      (extend the existing skill-intake end-to-end test rather than adding a second harness)

## 6. Docs, examples and the architecture model

- [x] 6.1 Write the ADR under `docs/architecture/decisions/` amending ADR 0050: knock signs
      standalone artifacts at admission; 0050's "admit is refused on a git source" is superseded.
      Link it to this change's spec. Verify it renders in the Structurizr Decisions pane
- [x] 6.2 Update the Component view in `docs/architecture/workspace.dsl` with the GitPlanner →
      attestor edge and refresh the committed Mermaid exports under `docs/architecture/_export/`;
      verify the export diff is non-empty and renders
- [x] 6.3 Update the skills example policy under `docs/examples/` to show `admit: true` on a git
      source, and the skills how-to to state what a signed skill does and does not carry
      (signature yes, attestation and SBOM no); verify the example policy parses with
      `uv run knock reconcile --dry-run-tags` against it
- [x] 6.4 Update `docs/how-to/verify-gate.md` to say `--require image-signature` applies to placed
      skills; keep the Diátaxis sidebar order intact

## 7. Gates

- [x] 7.1 Verify `uv run ruff check . && uv run ruff format --check . && uv run mypy knock` is clean
- [x] 7.2 Verify coverage gates hold:
      `uv run pytest --cov=knock --cov-report=term-missing --cov-fail-under=80` and
      `uv run pytest tests/unit/domain --cov=knock.domain --cov-fail-under=90`
- [x] 7.3 Verify `uv run pytest` is green end to end; `sign-image-at-admission` archived
      2026-09-20, and this change carries the `image-signature` delta retracting the git-source
      refusal that archive published — verified by `openspec validate --strict`
