# Proposal

## Why

knock's rebuild path promises hardening, and the governing dossier (docs `spec.md` §8.8.2) classes "critical CVE with a fix available" as *repairable by reconstruction*. Nothing in knock performs that repair: the three transform steps (`injectCA`, `rewritePackageSources`, `setTimezone`) re-point package sources, inject certificates and set a timezone, then rebuild on the same base without upgrading a single package. A flagged image therefore stays in service until upstream republishes. This change gives knock the missing verb: a fourth transform step that upgrades OS packages from the already-configured internal mirror, under a human-controlled trigger, so the promise becomes a step the policy can declare.

## What Changes

- New transform step `upgradePackages { epoch }`: a single `RUN` that upgrades every installed OS package through apt (Debian, Ubuntu) or apk (Alpine) via the mirror `rewritePackageSources` already pointed the image at. The `epoch` parameter is the human trigger (D-12 of the dossier): changing it changes `transform_version`, which makes `reconcile` plan a `rebuild` for every selected tag of the import.
- Validation of the step inside the existing closed vocabulary: `upgradePackages` is refused unless `rewritePackageSources` appears earlier in the same `transform` list (otherwise `apt-get upgrade` would reach public repositories, which the dossier's IF-05 forbids during a rebuild); `epoch` is required and pattern-restricted because it is interpolated into a `RUN`.
- Explicit failure, never silence: on an image with neither apt nor apk the `RUN` exits non-zero with a named message, so a signed lineage never claims an upgrade that did not happen.
- The rebuild path now preserves the source image's execution identity: when the source config declares a non-root `User`, the rendered Dockerfile switches to root for the transform `RUN`s and restores that user at the end. Root-equivalent sources (`""`, `root`, `0`, `0:0`, `root:root`) render byte-for-byte as today. The user value read from the untrusted source image is pattern-validated; a value outside the pattern fails the operation (`UnsafeSourceUserError`) instead of being rendered.
- `ImageInfo` gains `user` (default `""`), read from the OCI config by the regctl adapter, so the use case can pass it to the renderer.
- apt downloads during a rebuild wave share a BuildKit cache mount; the image's own apt configuration (`docker-clean`) is restored before the layer is committed.
- A generic example policy under `docs/examples/`, a spec and an ADR, and `make reference` regeneration, per repository conventions. `docs/roadmap.md` is not changed: the two-phase placement (staging) that gates production activation stays a separate design (see `TODOS.md`).

Not in this change: a Copacetic adapter (conditional, separate design), two-phase placement / staging, `verify --require repaired-since`, automatic epoch bumps driven by a verdict, multi-arch patching, any change to `reconcile-gate` requirements.

## Capabilities

### New Capabilities
- `transform-upgrade-packages`: the `upgradePackages { epoch }` transform step: what it upgrades, through which mirror, how the epoch triggers a rebuild of every selected tag, what the policy validation refuses, and how it fails on images it cannot upgrade.
- `rebuild-source-user`: the rebuild path's treatment of the source image's `User`: byte-identical Dockerfiles for root-equivalent sources, root-then-restore wrapping for non-root sources, and refusal of user values outside the safe pattern.

### Modified Capabilities
- (none) — `reconcile-gate` already plans an update caused by a transform change as a `rebuild`; its requirements do not change.

## Impact

- `knock/domain/transforms/steps.py` (new compiler), `registry.py` (tuple entry), `render.py` (ordering rule in `validate_transform_steps`, `source_user` rendering), `knock/domain/mirror_policy.py` (field description), `knock/errors.py` (`UnsafeSourceUserError` under `DomainError`).
- `knock/ports/registry.py` (`ImageInfo.user`), `knock/adapters/regctl_cli.py` (reads `config.User`), `knock/use_cases/reconcile_registry.py` (`_build_variant` passes the source user), `tests/fakes/registry.py`, `tests/fake-bins/regctl`.
- Published contracts: the `MirrorPolicy` JSON schema and `docs/reference/` (regenerated); the transform predicate `/v1` is unchanged (the step and its `epoch` appear in `steps[].params` as any other step).
- Operations: a `RUN --mount=type=cache` requires the deployed `buildkitd` to accept it (verified during implementation); an epoch change on a wide selection (e.g. `redis` `^7\.`) rebuilds hundreds of tags in one pass, accepted and documented, with the selection as the lever.
- Dependencies outside this repository: production activation of the step waits for the dossier's D-32 (two-phase placement), tracked in `TODOS.md`; the dossier repository corrects §8.8.2 and adds a guard in its own change.
