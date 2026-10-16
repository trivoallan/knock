# Tasks

> Release gate: implementation can merge to `main`, but shipping it needs a knock release, which
> the maintainer must authorize while the regis/knock freeze holds (until 2026-11-22).

## 1. Spike — check the premises against real tools

- [x] 1.1 Build a two-platform image with `buildctl --opt platform=linux/amd64,linux/arm64` and provenance on, into a local registry (binfmt registered); run `regctl image mod --replace --annotation k=v` on its tag and confirm the index gets the annotation and every child manifest digest is unchanged; record the commands and result in design.md D5 (or the index-only form needed if children change)
- [x] 1.2 On the same index, confirm `syft scan registry:<ref>@<index> --platform linux/arm64` describes the arm64 image, and that `regctl image copy --referrers` carries referrers of the index to another registry; record the result in design.md

## 2. Domain

- [x] 2.1 Add a pure platform helper (parse, normalise `arm64` ≡ `arm64/v8`, ignore `unknown/unknown`, set comparison) with unit tests covering the spec's variant scenario
- [x] 2.2 Validate `platforms` entries (pattern, no duplicates) on the policy model; unit tests for "Malformed platform" and "Duplicate platform"; `make reference` regenerates `docs/reference/` with the new constraints
- [x] 2.3 Remove the "multi-platform rebuild is not supported" refusal from `policy_merge`; turn its test into "a transform with several platforms loads"
- [x] 2.4 Add `PlatformUnavailableError` under `DomainError`; unit test that `exit_code_for` maps it to 1
- [x] 2.5 Give `MirrorArtifact` / `SourceArtifact` their platforms and teach `_classify` platform drift (known and different ⇒ `update`, no grace; unknown ⇒ no effect); unit tests for the three drift scenarios
- [x] 2.6 Add `{prefix}.sbom.platform` to `build_sbom_annotations` (omitted when no platform) and a pure coverage function "one SBOM per (format, platform), unannotated counts for a single platform, empty prefix ⇒ formats only"; unit tests for each case

## 3. Ports, adapters, fakes

- [x] 3.1 `ImageInfo.platforms`: `RegctlAdapter.inspect` fills it from the manifest it already fetches (index entries, or the config's os/arch for a plain manifest); integration test with the `regctl` fake-bin for an index, a plain manifest and an attestation-bearing index
- [x] 3.2 `BuildRequest.platforms: tuple[str, ...]`; `BuildkitAdapter` passes the comma-joined list; update the `buildctl` fake-bin and its integration test asserting the exact argv; update `FakeImageBuilderPort`
- [x] 3.3 `SbomGeneratorPort.generate(..., platform=None)`; `SyftAdapter` adds `--platform` when given; update the `syft` fake-bin, its integration test and `FakeSbomGenerator`

## 4. Use cases

- [x] 4.1 Resolve the desired platforms per variant (`platforms`, else `KNOCK_BUILD_PLATFORM`) and pass them to the build; use-case test: two-platform policy ⇒ one build request with both platforms in policy order; no `platforms` ⇒ the configured single platform
- [x] 4.2 Refuse at plan time a tag whose source lacks a desired platform: failed operation naming the missing platforms, no build, absent from `--plan-out`, other tags proceed; use-case tests for the one-shot and `--plan-out` modes
- [x] 4.3 Feed desired and placed platforms into the variant reconcile; use-case test: a mirror placed `[amd64]` with policy `[amd64, arm64]` ⇒ update planned; an upgraded run with no `platforms` ⇒ nothing planned
- [x] 4.4 Generate and attach one SBOM per (format, platform) for a multi-platform rebuild, all on the index digest; use-case test asserting four referrers with platform annotations for two formats × two platforms, and that one failure fails the operation
- [x] 4.5 Use the per-platform coverage function in `reconcile`'s SBOM backfill and in `promote`'s arrival check (refusal names format and platform); use-case tests for "Missing arm64 SBOM is backfilled", "Older single-platform image stays covered" and "Promotion refuses a missing platform SBOM"
- [x] 4.6 Update `KNOCK_BUILD_PLATFORM`'s description and the `platforms` field description; `make reference` and `make lint` pass with no drift

## 5. Docs

- [x] 5.1 Write ADR 0057 "Multi-platform rebuild" (thin, linking this change's design) and add it to the decisions index; drop multi-platform rebuild from *Deferred* in `docs/architecture/design.md`
- [x] 5.2 Extend `docs/examples/hardened/` with a two-platform transformed policy and its README walkthrough (amd64 listed first)
- [x] 5.3 Document binfmt/QEMU in `docs/how-to/rebuild-and-harden.md` and `docs/how-to/reference-deployment.md` (GitHub Actions, kind, native workers) and the empty-prefix coverage limit in `docs/how-to/inspect-sbom.md`
- [x] 5.4 Check `docs/architecture/workspace.dsl`: no new element expected; refresh `_export/` only if a description changes

## 6. Verification

- [x] 6.1 `make lint`, `make test` (≥ 90 % branch coverage) and `make image` pass
- [x] 6.2 End to end on kind with binfmt: reconcile a two-platform transformed policy, then `knock audit --sbom`, `knock verify` on the tag, and a staged run followed by `knock promote`; all report the index covered, and `regctl manifest get` shows amd64 then arm64
- [x] 6.3 Ask the maintainer to authorize the knock release (freeze until 2026-11-22) and hand `trivoallan/base-images` the policy and workflow changes from the Migration Plan
