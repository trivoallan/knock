# Design

## Context

See `proposal.md` for the motivation. What shapes the approach, as the code stands on `main`:

- `KNOCK_BUILD_PLATFORM` (`config.py`, default `linux/amd64`) is threaded through
  `reconcile` → `reconcile_registry` → `_build_variant` → `BuildRequest.platform: str | None`
  → `buildctl --opt=platform=<one>`.
- The policy field `platforms` (defaults and per import, `mirror_policy.py`) is merged by
  `policy_merge.py` and carried by `expand.py`, but **nothing reads it** apart from a load-time
  refusal of `transform` + more than one platform. The copy path runs `regctl image copy` on the
  whole index and ignores the field, although the 2026-05-22 policy-format design says it should
  honour it.
- A rebuild built with an attestor configured is already an **index**: BuildKit's provenance
  (`provenance=true`) adds `unknown/unknown` attestation manifests next to the one image manifest.
  The stamp (`regctl image mod --replace --annotation`) therefore already lands on an index, and
  `RegctlAdapter.inspect` already pins a concrete platform to read the config of such an index.
  Multi-platform output changes the number of image manifests, not the shape of what is stamped.
- `inspect` already fetches the manifest (index or image). Platforms can be read from it without
  any new registry call.
- syft is called as `syft scan registry:<repo>@<digest>` with no `--platform`; on an index it scans
  the platform of the host syft runs on (or its own default). The SBOM is attached as a referrer of
  the digest knock placed, and attested with cosign.
- Rebuild triggers live in `domain/reconcile._classify`: a different source digest (after the
  7-day grace) or a different `transform_version` (immediately). `transform_version` hashes steps
  and resolved resources only; the build platform is not part of it.
- `promote` checks, after copying a staged digest with its referrers, that one SBOM per format and
  the signed transform attestation arrived.

## Goals / Non-Goals

**Goals:**

- One build, one index, one digest that every piece of evidence binds to.
- Zero behaviour change for a policy that does not ask for several platforms, and no rebuild
  caused by the upgrade itself.
- Every refusal is explicit and early: a platform knock cannot build is named before any build.

**Non-Goals:**

- Per-platform signatures or attestations on child manifests.
- Choosing builders per architecture (native arm64 nodes). knock asks BuildKit; the deployment
  decides how BuildKit gets there.
- Fixing the copy path's handling of `platforms` (follow-up, see Open Questions).

## Decisions

### D1. The platform list comes from the policy's `platforms`, defaulting to `KNOCK_BUILD_PLATFORM`

The field exists, is already merged (import overrides defaults, replace-wholesale), and is a
per-image need: `base/python` wants arm64, most hardened images do not.

- *Alternative — make `KNOCK_BUILD_PLATFORM` a list.* Rejected: it is per deployment, so every
  rebuild of the deployment would pay the emulated build, and it cannot differ per image.
- *Alternative — all source platforms, filtered by the policy.* This is what the copy path's
  design says for an absent `platforms`. Rejected for the rebuild default: an official `python`
  index carries eight platforms, so the first run after the upgrade would rebuild every hardened
  image for all of them under emulation. Absent `platforms` keeps meaning "the configured single
  platform" on the rebuild path.

`KNOCK_BUILD_PLATFORM` keeps its name and gains the description "platform of a rebuild whose
policy declares no `platforms`".

### D2. A missing platform refuses the tag at plan time; no partial index

The policy-format design already set the principle: "no platform is silently dropped". The source
platforms are read during the plan (`to_source_artifact(registry.inspect(...))` gains the
platforms), so the plan phase can mark the tag as failed with a domain error
(`PlatformUnavailableError`, under `DomainError`, exit 1) naming the missing platforms. The tag
never reaches the plan file nor the builder, so `--plan-out` / `--apply-plan` and the one-shot
mode behave alike, and continue-on-error keeps the other tags going.

Matching normalises the platform: os and architecture must match; a variant is compared only when
the request names one; `arm64` with no variant equals `arm64/v8` (the OCI image-index spec's
canonical default). `unknown/unknown` attestation entries are ignored.

- *Alternative — build the intersection.* Rejected: the consumer asked arm64, would get an index
  without it and fail at pull on an arm64 node, far from the cause.
- *Alternative — fail at apply.* Rejected: an evaluator would judge, and a staging run would
  hold, a tag that can never be built.

### D3. One BuildKit invocation, comma-joined platforms

`BuildRequest.platform: str | None` becomes `platforms: tuple[str, ...]` (non-empty), and
`BuildkitAdapter` passes `--opt platform=linux/amd64,linux/arm64`. The dockerfile frontend builds
each platform from the same rendered Dockerfile and pushes one index. The rendered transforms
(`rewritePackageSources`, `upgradePackages`, CA certs) contain no architecture-specific input, so
one render serves every platform; a future step that needs one would read `TARGETPLATFORM`.

- *Alternative — one build per platform, then assemble the index with `regctl index create`.*
  Rejected: more code, a second write path, and BuildKit's per-platform provenance would have to be
  re-attached by hand.

### D4. Platform drift is read from the placed index, not hashed into `transform_version`

`ImageInfo` gains `platforms: tuple[str, ...]` (normalised, empty when unreadable).
`MirrorArtifact` gains the same, and `_classify` returns `update` (no grace) when the mirror's
platforms are known and differ, as a set, from the desired ones. The desired set is passed
alongside `desired_transform_version`.

- *Alternative — add the platform list to the `transform_version` hash.* Rejected either way it is
  done: hashing it always changes every recorded version, so the first run after the upgrade
  rebuilds every hardened image; hashing it only for multi-platform lists is a special case in a
  content hash, and still misses a change of `KNOCK_BUILD_PLATFORM`. Reading the placed state is
  the truth knock already uses for the source digest, and costs no extra call.

An image placed before this change is either an index carrying `KNOCK_BUILD_PLATFORM` (attestor
on) — equal to the desired set, no rebuild — or a plain manifest (attestor off), whose platforms
the manifest does not state — unknown, no rebuild.

### D5. All evidence binds to the index digest; SBOMs are per platform

The tag resolves to the index; `audit`, `verify`, `promote`, the blast-radius join and Kubernetes'
`imageID` all see that digest, and the index digest pins every child manifest. So:

- **Stamp**: on the index, unchanged code path (`annotate --replace` on the tag). Verified (task
  1.1, BuildKit v0.18.2 + QEMU, `registry:2`): `regctl image mod --replace --annotation` on a
  two-platform index with provenance writes the index annotation and leaves every child manifest
  digest, and BuildKit's attestation manifests pointing at them, unchanged.
- **Transform attestation**: one statement, subject = index digest, predicate
  `https://knock.dev/predicate/transform/v1` unchanged. No `platforms` field is added: the signed
  subject already commits to the list.
- **Signature**: `cosign sign` on the index digest, as today.
- **SBOM**: one per (format, platform), generated with `syft --platform <p>` against the index
  digest (verified with syft v1.52.0: `--platform linux/arm64` on the index scans the arm64 child;
  `regctl image copy --referrers` carries the index's referrers), attached as a referrer **of the index** with a new annotation `{prefix}.sbom.platform`,
  and attested as today. A single-platform image keeps one SBOM per format and gets the annotation
  too.

`SbomGeneratorPort.generate` takes an optional `platform`. A copy keeps one SBOM per format and is
counted per format: counting per platform there would re-scan every multi-arch index already
copied. Coverage (`reconcile`'s backfill and
`promote`'s arrival check) requires one referrer per (format, platform of the index); an
unannotated SBOM counts for an index with exactly one platform, so existing images stay covered.
With an empty `KNOCK_LABEL_PREFIX` no annotation can be written, and coverage falls back to
formats only (documented as a known limit; git stamps already require a prefix).

- *Alternative — SBOM referrers on each child manifest.* Rejected: `promote`, `audit --sbom` and
  `verify --require sbom` all ask the digest the tag resolves to; moving SBOMs to children would
  touch all three and the blast-radius join, for a scanner nobody runs per child today.
- *Alternative — one SBOM for the index (syft's default platform).* Rejected: arm64 packages are
  not described, and the result depends on where syft runs (amd64 CI vs arm64 laptop).
- *Alternative — `cosign sign --recursive`.* Deferred (Open Questions): no consumer verifies
  child digests today, and it multiplies signatures.

### D6. Platform strings are validated at load

`platforms` entries get a pattern (`^[a-z0-9_]+/[a-z0-9_]+(/[a-z0-9_]+)?$`) and a uniqueness check
on the Pydantic model, so the JSON Schema and `docs/reference/` carry them. The value reaches
`buildctl` as an argument list (no shell), so this is about early, named errors, not injection.

### D7. QEMU is a deployment concern, documented, not automated

knock's image does not register binfmt handlers (that needs a privileged container and is a
host-kernel setting). The deployment guide gains: GitHub Actions — `docker/setup-qemu-action`
before starting `buildkitd`; kind — a privileged `tonistiigi/binfmt --install arm64` run once per
node; production — prefer native arm64 BuildKit workers when build time matters. A missing
emulator surfaces as a `buildctl` failure (`exec format error`) → `BuildkitError`, exit 2, for that
tag only.

### D8. No knock rule about amd64

regis 0.38/0.39 mis-handle a rebuild without a `linux/amd64` variant (#870). That is a regis bug;
knock does not encode it. The `base-images` policy lists `linux/amd64` first, and D1's ordering
guarantee keeps it first in the index.

## Risks / Trade-offs

- [`regctl image mod` rewrites child manifests] → task 1.1 checks it against a real two-platform
  BuildKit index before any other work; if it does, stamp with an explicit index-only form.
- [Emulated builds are slow and can time out in CI] → documented; the build timeout is the
  orchestrator's; native workers are the long-term answer.
- [A source's arm64 image differs from its amd64 image in packages] → precisely why SBOMs are
  per platform.
- [regis judges one platform] → regis reads the index; its per-platform behaviour is regis's
  concern. Recorded for the KR2 bench: a regis `incomplete` on a multi-platform rebuild may come
  from platform selection.
- [Four SBOM referrers + four SBOM attestations per tag instead of two] → registry storage grows
  linearly with platforms; acceptable for the handful of multi-platform hardened images expected.
- [Empty label prefix loses per-platform coverage] → documented limit; the default prefix is set.

## Migration Plan

1. Release knock with this change (minor). **Blocked by the release freeze until 2026-11-22
   unless the maintainer authorizes it.**
2. Deployments that will build foreign platforms register binfmt on their BuildKit hosts.
3. `trivoallan/base-images` adds `platforms: [linux/amd64, linux/arm64]` to its `base/python`
   policy, adds `docker/setup-qemu-action` to its screening workflow, and bumps the knock image.
   The next screening rebuilds that tag once (platform drift, D4), regis judges, promote places.
4. regis, knock and uske switch their `FROM` (workspace change `dogfood-base-images`, group 3).

Rollback: remove `platforms` from the policy (next run rebuilds single-platform via drift), or pin
the previous knock image; images already placed keep their evidence.

## Open Questions

- Should `platforms` be honoured on the copy path, as the 2026-05-22 design says? Separate change:
  it changes what existing copy policies place.
- Should the reconcile plan document list the platforms of a rebuild operation, so an evaluator
  sees what will be built? Additive to the plan schema; can follow once an orchestrator asks.
- `cosign sign --recursive` for child manifests, if a consumer ever verifies by child digest.
