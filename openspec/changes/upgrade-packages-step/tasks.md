# Tasks

## 1. Foundations

- [x] 1.1 Read the `buildkitd` version in `deploy/overlays/local` (and the production target if reachable) and record in `design.md` that it accepts `RUN --mount=type=cache` without a `# syntax=` directive; stop and raise the daemon version first if it does not
- [x] 1.2 Write the regression test before any change: render the `docs/examples/hardened/redis.yml` transform list (`injectCA` + `rewritePackageSources`) with an empty source user and freeze both the exact Dockerfile text and `transform_version` in `tests/unit/domain/transforms/test_render.py` / `test_version.py`; run it green on `main` so it guards every later step

## 2. Domain: the step

- [x] 2.1 `knock/domain/transforms/steps.py`: `UpgradePackages` compiler with a Pydantic params model (`epoch` required, pattern `^[A-Za-z0-9._-]{1,64}$`, `extra="forbid"`); fragment assembled from a list of shell parts into one `RUN --mount=type=cache,target=/var/cache/apt,sharing=locked` per design D2 (epoch marker, apt branch with `DEBIAN_FRONTEND`, `docker-clean` moved aside and restored, keep-cache snippet added and removed, `Always-Include-Phased-Updates`, `rm -rf /var/lib/apt/lists/*`; apk branch; `else echo … >&2; exit 1`); verify with `tests/unit/domain/transforms/test_steps.py` asserting the exact `RUN` text for the three branches
- [x] 2.2 `knock/domain/transforms/registry.py`: add `UpgradePackages()` to `BUILTIN_STEPS`; verify `test_registry.py` lists the four names
- [x] 2.3 `knock/domain/transforms/render.py` `validate_transform_steps`: refuse `upgradePackages` without `rewritePackageSources` earlier in the same list, error naming both steps; verify in `test_validate.py` with the three cases (after: accepted; before: refused; absent: refused) plus `epoch` refusals (`;`, space, quote, 65 chars, missing)
- [x] 2.4 `tests/unit/domain/transforms/test_version.py`: a changed `epoch` changes `transform_version`; the same `epoch` keeps it; verify green

## 3. Domain + ports: the source user

- [x] 3.1 `knock/errors.py`: `UnsafeSourceUserError(DomainError)`; verify `tests/unit/test_errors.py` maps it to exit code 1
- [x] 3.2 `knock/domain/transforms/render.py` `render(…, source_user="")`: no `USER` lines for `""`, `root`, `0`, `0:0`, `root:root`; `USER root` after `FROM` and `USER <value>` after the last fragment otherwise; values outside `^[A-Za-z0-9._-]{1,64}(:[A-Za-z0-9._-]{1,64})?$` raise `UnsafeSourceUserError` before rendering; verify in `test_render.py`: the five root-equivalent values render byte-identically to task 1.2's frozen text, `app` and `1000:1000` are wrapped, `app\nRUN x`, `a b` and a 65-character name are refused
- [x] 3.3 `knock/ports/registry.py`: `ImageInfo.user: str = ""`; `knock/adapters/regctl_cli.py` `inspect`: read `config.User` (string, else `""`); verify `tests/integration/test_regctl_cli.py` with a new `tests/fake-bins/regctl` scenario returning a `User` and one without
- [x] 3.4 `tests/fakes/registry.py`: seed `user` on `ImageInfo`; verify existing fake tests still pass unchanged (default `""`)

## 4. Use case

- [x] 4.1 `knock/use_cases/reconcile_registry.py` `_build_variant` / `_do_import`: pass `source[w.src_tag].user` to `render`; verify in `tests/unit/use_cases/test_reconcile.py` that the journaled Dockerfile ends with `USER app` for a fake registry seeded with `user="app"`, and has no `USER` line for the default
- [x] 4.2 `tests/unit/use_cases/test_reconcile.py`: a policy with `rewritePackageSources` + `upgradePackages { epoch }` plans `import`, then a changed `epoch` plans `update` for every selected tag, then the same `epoch` plans `keep`; `FakeImageBuilder(fail=True)` marks the operation failed and pushes nothing; verify green
- [x] 4.3 `tests/unit/use_cases/test_reconcile.py`: a source whose fake `user` is `"app\nRUN x"` yields a failed operation naming the value, no build request; verify green
- [x] 4.4 Run `uv run pytest tests/unit/domain --cov=knock.domain --cov-fail-under=90` and `uv run pytest --cov=knock --cov-fail-under=80`; `uv run mypy knock`; `uv run ruff check . && uv run ruff format --check .`; all green

## 5. Example, schema and docs

- [x] 5.1 `knock/domain/mirror_policy.py`: extend the `TransformStep.name` description with `upgradePackages`; run `make reference` and verify `docs/reference/` regenerates without drift in CI terms (`git diff --stat docs/reference`)
- [x] 5.2 `docs/examples/repaired/redis.yml` + a README walkthrough: a public image, `rewritePackageSources` then `upgradePackages { epoch }`, no organisation-specific reference; verify `tests/unit/use_cases/test_examples_schema.py` accepts it and `knock reconcile docs/examples/repaired --plan-out` renders a plan locally
- [x] 5.3 ADR `docs/architecture/decisions/0054-upgrade-packages-step.md` with the three runbooks (wave too long: narrow the selection; `no apt-get or apk` every pass: remove the step or route to copy; `UnsafeSourceUserError`: route to copy) and the rollback path (removing the step costs one rebuild wave), linking this change's proposal and design as ADRs 0050 to 0053 do; verify the file exists and its links resolve. Amended during apply: no separate `docs/superpowers/specs/` file, since every change since 2026-09 keeps its design in `openspec/changes/` and the ADR links there; a second copy of `design.md` would drift
- [x] 5.4 Confirm the C4 model needs no change (no new port or adapter) and note it in the ADR; verify `docs/architecture/workspace.dsl` is untouched in the diff

## 6. Local verification

- [x] 6.1 Real run of `knock reconcile --plan-out` then `--apply-plan` from the runtime image built on this branch, against a throwaway registry and `moby/buildkit:v0.30.0-rootless` (the local overlay's daemon), public repositories standing in for the mirror; `regis analyze -a cve` with the dossier's version playbook on each source and rebuilt digest. Amended during apply: not `make up-local` (it git-syncs policies from GitHub, so it cannot see an unpushed branch). Measured on 2026-10-10: redis:7.2.0 53 packages upgraded, nginx-unprivileged:1.25.3 69 (user `101` restored), ubuntu:jammy-20230308 60, alpine:3.18.0 9; apt configuration identical to the source on all three apt images, no leftover file; busybox:1.36.0 fails with the named message and nothing is pushed. `regis` (grype database of 2026-06-26, not refreshed: the host disk was full): fixable findings on OS packages go to 0 on all four; `cve-fixable` passes on nginx, ubuntu and alpine, `cve-critical` passes on ubuntu and alpine. The original criterion (both rules pass wherever the source failed them) does NOT hold on redis: 238 fixable findings remain on the `redis` binary and the Go modules of `gosu`, which are not OS packages, and 7 to 8 critical Debian findings have no fix. Recorded as a consequence in ADR 0054
- [x] 6.2 Run `knock reconcile --plan-out` on the unchanged existing local policies and verify the plan is `keep` everywhere (no spurious rebuild from the renderer change)
- [x] 6.3 Commit `TODOS.md` (two-phase placement design, `verify --require repaired-since`, demo act 3) on this change's branch; verify it is in the PR
