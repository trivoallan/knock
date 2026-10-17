# Tasks

No `design.md`: the change is one setting, one validator and one cosign flag in a single module,
with no new dependency and no open design question (the `key`/`kms` refusal is settled in the
proposal).

## 1. Setting and validation

- [ ] 1.1 In `tests/unit/test_config.py`, add failing tests: `KNOCK_ATTEST_VERIFY_GITHUB_REPOSITORY`
      parses from the environment into `Settings().attest.verify_github_repository`; it defaults to
      empty; with `KNOCK_ATTEST_SIGNER=key` (and a key ref) or `kms`, setting it raises a
      validation error whose message names both `KNOCK_ATTEST_VERIFY_GITHUB_REPOSITORY` and the
      signer; with `keyless` it is accepted. Verify they fail:
      `uv run pytest tests/unit/test_config.py -k github_repository --no-cov`.
- [ ] 1.2 In `knock/config.py`, add `verify_github_repository` to `AttestSettings` (description:
      keyless verify, cosign `--certificate-github-workflow-repository`, `owner/name`), the flat
      `attest_verify_github_repository` field on `Settings`, its mapping in `Settings.attest`, and
      a validator on `AttestSettings` refusing it with `kms`/`key`. Verify the 1.1 tests pass and
      `test_attest_schema_is_serializable_and_lists_fields` still passes.
- [ ] 1.3 Verify the refusal surfaces as exit 3 from the CLI: add a test in the existing CLI test
      module that runs a command with `KNOCK_ATTEST_SIGNER=key`, a key ref and the repository set,
      and asserts exit code 3 with both setting names in the error. Verify it passes.

## 2. cosign verification

- [ ] 2.1 In `tests/integration/test_cosign_cli.py` (fake `cosign` from `tests/fake-bins`), add
      failing tests: with `keyless` and the repository set, `verify_signature`, `has_attestation`
      and `verify` each invoke cosign with `--certificate-github-workflow-repository <value>`
      after the identity and issuer flags; with the repository empty, none of them passes the
      flag; with `key`, the flag never appears. Verify they fail.
- [ ] 2.2 In `knock/adapters/cosign_cli.py`, extend `_verify_args` for keyless only: append
      `--certificate-github-workflow-repository` and the value when it is non-empty. Verify the
      2.1 tests pass.
- [ ] 2.3 Prove the binding against a real certificate, once: with the `cosign` of the knock image,
      run `cosign verify` on an image signed keyless by uske's bench
      (`ghcr.io/trivoallan/uske-example/alpine-repaired:3.22.1`) with the bench's identity and
      issuer, first with `--certificate-github-workflow-repository trivoallan/uske` (expect
      success), then with `mallory/uske` (expect failure). Record both commands and outcomes in
      the PR description. If the extension is missing from the certificate, stop and report: the
      approach would not hold.

## 3. Documentation

- [ ] 3.1 Run `make reference` and verify `docs/reference/configuration.md` and
      `docs/reference/config.schema.json` gain the `KNOCK_ATTEST_VERIFY_GITHUB_REPOSITORY` row and
      nothing else changes.
- [ ] 3.2 In `docs/how-to/verify-gate.md`: replace the sentence saying that without identity and
      issuer cosign "applies its default certificate-identity check" with the actual behaviour
      (keyless verification fails, so the gate fails closed); add the new setting to the keyless
      example and the Argo snippet, with one paragraph on reusable workflows (the identity names
      the called workflow; the repository binding names the caller). Verify the page renders and
      its links resolve.

## 4. Closing

- [ ] 4.1 Run the full suite with its coverage gates and the strict type check: `uv run pytest`
      and `uv run mypy knock` both pass; `uv run ruff check . && uv run ruff format --check .`
      pass.
- [ ] 4.2 Run `openspec validate keyless-caller-repository --strict` and verify it reports the
      change as valid.
- [ ] 4.3 Open the PR with a Conventional Commit title, for example
      `feat(adapters): bind a keyless signature to the GitHub repository that ran it`, and note the
      uske follow-up (pass `KNOCK_ATTEST_VERIFY_GITHUB_REPOSITORY` from `extra-screen.yml`, which
      closes uske's `RISK-09`).
