# 57. Rebuild every platform a policy declares, under one index

Date: 2026-10-16

## Status

Accepted.

Lifts the single-platform limit of the rebuild path set by the transform design
(`docs/superpowers/specs/2026-06-11-image-transform-hardening-design.md`). Full design:
`openspec/changes/rebuild-multi-platform/design.md` (archived under
`openspec/changes/archive/` once released).

## Context

A transformed import was built for `KNOCK_BUILD_PLATFORM` only, and a policy asking a transform
for more than one platform was refused at load. The copy path places the whole upstream index,
so a hardened image was single-arch while a copied one was multi-arch: a hardened image could not
serve as a base for anything published for `linux/amd64` and `linux/arm64`. The policy field
`platforms` existed, was merged, and was read by nothing but that refusal.

## Decision

- **The platforms of a rebuild are the policy's `platforms`** (import, else defaults), in the
  order declared; absent, the single `KNOCK_BUILD_PLATFORM`, as before. Entries are validated
  (`os/arch[/variant]`, no duplicates).
- **One BuildKit build, one index.** `buildctl --opt platform=a,b` builds each platform from the
  same rendered Dockerfile and pushes one OCI index.
- **A source lacking a platform is refused, never narrowed.** The tag's operation fails at plan
  time (`PlatformUnavailableError`, exit 1), names the missing platforms, and never reaches the
  plan file or the builder. `linux/arm64` and `linux/arm64/v8` are one platform. A source whose
  platforms cannot be read is not refused on that ground: the build is the check.
- **Platform drift is read from the placed index**, not hashed into `transform.version`: when the
  platforms a placed rebuild carries differ from the platforms its policy asks, the tag is
  rebuilt at once. Unreadable placed platforms trigger nothing, so upgrading knock rebuilds
  nothing.
- **Evidence binds to the index digest**: stamp, transform attestation (predicate unchanged) and
  signature, as before. **SBOMs are per platform**: one per format and platform, generated with
  `syft --platform`, attached to the index and annotated `{prefix}.sbom.platform`. `reconcile`'s
  backfill and `promote`'s arrival check count a rebuild's SBOMs per platform; an unannotated SBOM
  counts for a single-platform index; a copy is counted per format, as before.
- **Emulation is a deployment concern.** knock asks BuildKit for the platforms; the BuildKit host
  registers binfmt emulators or provides native workers.

## Consequences

- A hardened image can be a multi-arch base. `linux/amd64` listed first stays first in the index.
- A deployment building a foreign platform needs binfmt on its BuildKit host
  (`docker/setup-qemu-action`, `tonistiigi/binfmt --install arm64`); emulated builds are several
  times slower, and a missing emulator fails that tag with a `BuildkitError` (exit 2).
- A two-platform rebuild with two SBOM formats carries four SBOM referrers and four SBOM
  attestations.
- With an empty `KNOCK_LABEL_PREFIX` no platform annotation can be written, and SBOM coverage
  falls back to formats only.
- The copy path still ignores `platforms` (it copies the whole index); honouring it is a separate
  change. Child manifests are not signed (`cosign --recursive` is not used).
- Verified with BuildKit v0.18.2 (`moby/buildkit`, QEMU), `registry:2`, regctl and syft v1.52.0:
  `regctl image mod --annotation` on the index leaves every child manifest and BuildKit's
  attestation manifests untouched; `syft --platform linux/arm64` on the index scans the arm64
  image; `regctl image copy --referrers` carries the index's referrers.
