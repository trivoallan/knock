# Tasks

## 1. Verify the premise with real tools

- [x] 1.1 Create branch `feat/stage-and-promote-rebuilds` from `main`. With two local registries, the runtime image and a rootless BuildKit daemon, rebuild one image as today, then `regctl image copy --referrers` it by digest to the second registry; verify the digest is identical, the SBOM referrers and attestations are listed on it there, and `knock verify` passes against the second registry. Also verify that the copy accepts a digest-only destination (`repo@sha256:...`) and that the tag can then be written inside the destination repository. Record the exact flags needed (`--referrers`, `--digest-tags`) and the tool versions in `design.md` decision 6. If it does not hold, stop and revise decisions 2 and 6 before any other task
- [x] 1.2 Tear the trial stack down; verify `docker ps -a` and `docker network ls` show nothing of it

## 2. ADR first

- [ ] 2.1 Write `docs/architecture/decisions/0055-stage-and-promote-rebuilds.md` (status proposed) from `design.md`, linking this OpenSpec change as ADRs 0050 to 0054 do, and stating the staging volume sizing rule (the unique blobs of one pass, base layers included) and that the staging registry must not be one consumers pull from; verify the docs site builds (`npm run build` in `website/`)

## 3. Domain: the staged rebuilds document

- [x] 3.1 Failing tests then, in the existing `knock/domain/gate.py`: `StagedEntry` (with its `aliases` list) and `StagedRebuilds` (frozen, camelCase, `extra="forbid"`), `staged_rebuilds_json_schema()`; verify round-trip, unknown-field rejection and schema tests pass
- [x] 3.2 Failing tests then, in the same module, a pure function that re-roots a destination repository under the staging host, and one that says whether an operation stages (it builds) or not (copy path); verify with table tests including two destinations of one policy
- [x] 3.3 Add `StagedDigestMismatchError` under `AdapterError` in `knock/errors.py`; verify `exit_code_for` returns 2 for it and the error-hierarchy test lists it

## 4. Ports and adapters: copy with referrers

- [x] 4.1 `RegistryPort.copy(src, dst, *, referrers=False)`; update `FakeRegistryPort` to journal the flag and to carry seeded referrers when it is set; verify existing use-case tests still pass unchanged
- [x] 4.2 `RegctlAdapter.copy` adds the flags recorded in 1.1 when `referrers=True`; extend the `regctl` fake-bin and the integration test to assert the exact argv in both cases
- [x] 4.3 `Counts.staged` and the `staged` operation kind in the reporter port, `StructlogReporter` and the CLI summary renderer; verify the rendered summary line shows `staged=N` and existing summary tests are updated

- [x] 4.4 Failing integration tests then the fix of design decision 9 in `CosignAdapter`: private key file (a `public-key` call, then `--key` on the derived file), public key file (used as is, no derivation), derivation failure (`CosignError`), KMS unchanged; extend the `cosign` fake-bin with `public-key`; verify the tests pass and the existing verify tests still do

## 5. Use case: staging during apply

- [ ] 5.1 Failing use-case tests for spec requirement "Building operations are staged instead of placed" (import with transforms staged, rebuild of a placed tag leaves it in service, copy-path import placed directly, `admit: true` staged image attested and not signed, dry-run tags stage nothing), then route building operations to the staging reference in `reconcile_registry.py`; verify the tests pass
- [ ] 5.2 Failing test then reuse of the withheld-import alias rule for staged tags (spec requirement "An alias never moves onto a staged tag"); verify the test passes
- [ ] 5.3 Failing tests then collection of staged entries and their return to the caller, including "one build failure, one entry", "attestation fails after the push, no entry", "nothing to stage", and the aliases recorded on the entry of the tag they designate; verify the tests pass
- [ ] 5.4 Failing test for "An unpromoted operation is planned again" (a second `--plan-out` after an unpromoted staged import plans it again); verify it passes without further code, or fix what prevents it

## 6. Use case: promotion

- [ ] 6.1 Failing tests then `knock/use_cases/promote.py` for the happy path: copy by digest with referrers, verification at the destination (SBOM referrers, signed attestation when a signer is configured, and the no-signer case), tag written last, `imported` / `updated` reported, signed when `admit: true`, second run on the same file a no-op; verify the tests pass
- [ ] 6.2 Failing tests then every refusal of spec requirement "promote refuses an entry it cannot trust" (policy missing, destination not declared, staged reference outside the staging registry, digest changed, image gone, stamp naming another policy, referrers lost by the copy, undeclared alias), each leaving the destination untouched and the other entries promoted; verify the tests pass
- [ ] 6.3 Failing tests then the recorded aliases written after the tag (promoted tag becomes the target, an alias of a removed entry is not written and is not moved by other entries); verify the tests pass
- [ ] 6.4 Run the entries through the stage executor reconcile already uses, so a pass with many entries does not promote one at a time; verify with a use-case test of several entries that results keep their order and one failure does not stop the others

## 7. CLI

- [ ] 7.1 `--stage-to` and `--staged-out` on `reconcile`, with the refusals of spec requirement "Staging options are refused when incomplete" mapped to `ConfigError`; write the file after the run; verify with CLI tests for each refused combination (exit 3) and for a written file
- [ ] 7.2 `knock promote <dir> --staged <file>` wired through `cli/_di.py`, invalid file mapped to exit 3, empty file exits 0; decide `--dry-run-tags` by following `reconcile`; verify with CLI tests
- [ ] 7.3 Run `make reference`; verify the CLI reference lists the new options and verb, `docs/reference/schemas/staged-rebuilds.*` exists, and the published-schema test passes

## 8. Real run

- [ ] 8.1 On a local stack (destination registry, staging registry, rootless BuildKit, runtime image from this branch): plan, apply with staging, check the destination is empty and the staged image carries stamp, SBOM and attestations, remove one of two entries from the file, promote; verify the kept tag is in the destination with the staged digest and its referrers, the removed one is absent, the alias points to the kept tag, and a second `--plan-out` plans the removed import again
- [ ] 8.2 Same stack: delete a staged image before promotion; verify that entry fails, the others are promoted and the exit code is non-zero. Then tear the stack down and verify nothing of it remains

## 9. Docs and close

- [ ] 9.1 Extend the gate example under `docs/examples/gate/` and its reference page with the two-phase walkthrough (apply with staging, evaluate, promote), stating that the staging registry must not be one consumers pull from; verify the example policies still pass `tests/unit/use_cases/test_examples_schema.py`
- [ ] 9.2 Add a Deployment view with a staging registry to `docs/architecture/workspace.dsl` and refresh the Mermaid exports under `docs/architecture/_export/`; verify the export is regenerated and committed
- [ ] 9.3 Update `docs/roadmap.md` (two-phase placement leaves "design and ADR only"), ADR 0054 (its precondition now has an answer), and remove the two-phase entry from `TODOS.md`; set ADR 0055 to accepted with the versions verified in 8.1
- [ ] 9.4 `uv run pytest` with both coverage gates, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy knock`, `npm run build` in `website/`, and `openspec validate stage-and-promote-rebuilds --strict`; verify all exit 0
