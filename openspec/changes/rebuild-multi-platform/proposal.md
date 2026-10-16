# Proposal

## Why

The rebuild path (an import with `transform` steps) builds for one platform only,
`KNOCK_BUILD_PLATFORM` (default `linux/amd64`), and a policy that asks a transform for more than
one platform is refused at load. The copy path places the whole upstream index, so today a
*hardened* image is single-arch while a *copied* one is multi-arch. That blocks a hardened image
from serving as a base for anything published multi-arch: regis, knock and uske ship
`linux/amd64` + `linux/arm64`, so they cannot move their `FROM` onto the `base/python` image that
knock rebuilds for them. The maintainer chose to keep that image on the rebuild path (its judged
rebuilds feed the regis/knock bench), so the rebuild has to learn to produce several platforms.

## What Changes

- A transformed import builds every platform its policy declares in `platforms` (defaults or
  per import) in one BuildKit build, and places **one OCI index** carrying one image manifest per
  platform. The load-time refusal of "transform with more than one platform" is lifted.
- When `platforms` is absent, a rebuild still builds the single `KNOCK_BUILD_PLATFORM`. No
  existing policy changes output; nothing is rebuilt merely because knock was upgraded.
- A source that lacks a requested platform is refused for that tag at plan time, by name. knock
  never builds a smaller index than the policy asked for.
- Platform drift triggers a rebuild: when the platforms of a placed rebuild differ from the
  platforms its policy now asks, the variant is updated, like a transform change and without the
  grace window. A placed image whose platforms cannot be read is left alone.
- The evidence stays bound to the index digest: the stamp, the transform attestation and the
  signature are on the index (as today); syft generates **one SBOM per platform and format**,
  each attached to the index and annotated with its platform. `promote` and `reconcile`'s SBOM
  backfill count coverage per platform; `knock verify --require sbom` keeps asking for any SBOM.
- Platform strings in a policy are validated (`os/arch[/variant]`, no duplicates).
- QEMU/binfmt for foreign platforms stays a deployment concern: knock asks BuildKit for the
  platforms; the BuildKit daemon's host provides the emulators. The deployment docs say how.

Not in this change: honouring `platforms` on the copy path (it copies the whole index today,
contrary to the 2026-05-22 design; recorded as a follow-up), a native builder per architecture,
signing child manifests (`cosign --recursive`), and any rule that a rebuild must contain
`linux/amd64` (that need comes from a regis bug, #870, and belongs in the policy, not in knock).

> [!IMPORTANT]
> Implementing this change needs a **knock release** (a minor: new behaviour behind an existing
> policy field). knock and regis are under a release freeze until **2026-11-22**: the maintainer
> must authorize the release, or the work waits for the freeze to lift. Planning and merging to
> `main` without a release are not blocked.

## Capabilities

### New Capabilities

- `multi-platform-rebuild`: building a transformed import for several platforms under one OCI
  index, choosing those platforms, refusing a source that lacks one, detecting platform drift,
  and keeping the per-platform evidence (SBOM) complete and checked.

### Modified Capabilities

None. `image-signature` keeps its requirements: the signature is on the digest the tag resolves
to, which is the index. `coverage-report` names SBOM formats found, which per-platform SBOMs do
not change. The in-flight `staged-rebuild` capability (change `stage-and-promote-rebuilds`, not
archived yet) is extended through this capability's promotion requirement rather than as a delta
on a spec that does not exist under `openspec/specs/` yet.

## Impact

- **Policy schema**: no new field; `platforms` changes meaning on a transformed import, and gains
  a pattern and uniqueness check. Generated reference (`docs/reference/`) changes.
- **Config**: `KNOCK_BUILD_PLATFORM` becomes the default for a rebuild without `platforms`.
- **Domain**: `policy_merge` drops its refusal; `reconcile._classify` learns platform drift;
  a small platform-normalisation helper; SBOM annotations gain a platform key.
- **Ports / adapters**: `BuildRequest.platform` becomes `platforms: tuple[str, ...]`
  (`buildctl --opt platform=a,b`); `ImageInfo` gains `platforms` (read from the manifest already
  fetched — no extra registry call); `SbomGeneratorPort.generate` takes a platform
  (`syft --platform`). Fakes and fake-bins follow.
- **Use cases**: `reconcile_registry` (build, SBOM loop, plan-time refusal, drift) and `promote`
  (per-platform SBOM check).
- **Docs**: ADR 0057, `design.md` drops multi-platform rebuild from *Deferred*, a worked example
  (`docs/examples/hardened/`), the deployment guide (binfmt). C4: no new element.
- **Operators**: a BuildKit daemon building a foreign platform needs binfmt emulators registered
  on its host (e.g. `tonistiigi/binfmt --install arm64`, `docker/setup-qemu-action` on GitHub
  Actions). Emulated builds are several times slower.
- **Downstream**: unblocks group 3 of the workspace change `dogfood-base-images` (regis, knock and
  uske `FROM base/python`) once `trivoallan/base-images` declares
  `platforms: [linux/amd64, linux/arm64]` (amd64 first, for regis #870).
