# Spec Delta

## Purpose

Lets a hardened (transformed) image be placed for several platforms under one OCI index, so it can
serve as a base for images published multi-arch, while every piece of evidence knock attaches
stays bound to what the tag resolves to and complete for each platform.

## ADDED Requirements

### Requirement: A transformed import builds every platform its policy declares

When a variant has `transform` steps and its resolved `platforms` (import, else defaults) lists one
or more platforms, knock SHALL build that variant for each listed platform and place a single OCI
index, under the output tag, that carries one image manifest per listed platform and no other
runnable platform. The index SHALL list the platforms in the order the policy declares them. When
`platforms` is absent, knock SHALL build the single platform configured by `KNOCK_BUILD_PLATFORM`,
as before this change.

#### Scenario: Two platforms

- **WHEN** a transformed import declares `platforms: [linux/amd64, linux/arm64]` and its source carries both
- **THEN** the output tag resolves to an index with exactly one `linux/amd64` and one `linux/arm64` image manifest, `linux/amd64` first

#### Scenario: No platforms declared

- **WHEN** a transformed import declares no `platforms` and `KNOCK_BUILD_PLATFORM` is `linux/amd64`
- **THEN** the output carries the single platform `linux/amd64`, as before this change

#### Scenario: A transform with several platforms loads

- **WHEN** a policy combines `transform` steps with more than one entry in `platforms`
- **THEN** the policy loads without error

### Requirement: Policy platforms are well-formed

knock SHALL refuse at load, as a policy validation error, a `platforms` entry that is not of the
form `os/arch` or `os/arch/variant` (lowercase letters, digits and underscores in each segment),
and a `platforms` list that names the same platform twice.

#### Scenario: Malformed platform

- **WHEN** a policy declares `platforms: [amd64]`
- **THEN** loading fails with a policy validation error naming the entry (exit 1)

#### Scenario: Duplicate platform

- **WHEN** a policy declares `platforms: [linux/arm64, linux/arm64]`
- **THEN** loading fails with a policy validation error

### Requirement: A source missing a requested platform is refused, not narrowed

When the source of a transformed variant does not carry every platform the variant asks for, knock
SHALL NOT build or place that tag. It SHALL record the operation as failed, naming the missing
platforms, before any build starts, and SHALL go on with the other operations. A platform counts as
carried when the source index lists an image manifest for the same os and architecture, and the
same variant when the request names one; `linux/arm64` and `linux/arm64/v8` are the same platform.
A source that is a single image manifest carries exactly the platform its configuration declares.
A source whose platforms cannot be read SHALL NOT be refused on that ground; the build then decides.

#### Scenario: Source lacks arm64

- **WHEN** a transformed import asks `[linux/amd64, linux/arm64]` and the source tag is an amd64-only image
- **THEN** that tag's operation fails with a message naming `linux/arm64`, nothing is built for it, and the run exits non-zero

#### Scenario: arm64 variant spelling

- **WHEN** the policy asks `linux/arm64` and the source index lists `linux/arm64/v8`
- **THEN** the platform is carried and the build proceeds

#### Scenario: Refusal appears in the plan

- **WHEN** `reconcile --plan-out` runs on such a source
- **THEN** the written plan contains no operation that would build that tag, and the run reports the refusal

### Requirement: Platform drift triggers a rebuild

When a transformed variant is already placed and the set of platforms its placed index carries
differs from the set its policy now asks, knock SHALL plan an update of that tag, without waiting for
the source grace window, as it does when the resolved transform changes. The platforms of a placed
image are those its index lists, or, for a plain image manifest, the one its configuration declares.
When they cannot be read, knock SHALL NOT plan an update for that reason alone.

#### Scenario: arm64 added to the policy

- **WHEN** a tag was placed for `[linux/amd64]` and the policy now asks `[linux/amd64, linux/arm64]`
- **THEN** the next reconcile plans an update of that tag, even though source and transform are unchanged

#### Scenario: Upgrade does not rebuild everything

- **WHEN** knock is upgraded to this version and a policy without `platforms` reconciles a tag placed earlier for `KNOCK_BUILD_PLATFORM`
- **THEN** no update is planned for that tag

#### Scenario: Unreadable platforms

- **WHEN** a placed rebuild declares no platform, neither in an index nor in its configuration
- **THEN** no update is planned on account of platforms

### Requirement: Provenance stays bound to the index

For a multi-platform rebuild, knock SHALL place the provenance stamp, the transform attestation
(`https://knock.dev/predicate/transform/v1`) and, when the policy admits, the image signature on
the index digest the output tag resolves to, with the same keys and predicate as a single-platform
rebuild. The predicate type and its fields SHALL NOT change.

#### Scenario: Stamp on the index

- **WHEN** a two-platform rebuild is placed
- **THEN** the index the tag resolves to carries `org.opencontainers.image.base.digest` and the `{prefix}.*` stamp, and `knock audit` reports it covered

#### Scenario: One attestation for the index

- **WHEN** a two-platform rebuild is placed with an attestor configured
- **THEN** exactly one transform attestation is attached, whose subject is the index digest, and `knock verify` on the tag accepts it

### Requirement: Every platform gets its own SBOM

For a rebuild carrying several platforms, knock SHALL generate one SBOM per configured format and
per platform, describing that platform's image, attach each as a referrer of the index digest, and,
when the label prefix is non-empty, annotate each with `{prefix}.sbom.platform` naming its platform.
A failure to generate or attach any of them SHALL fail the operation, as for a single-platform
image. A single-platform image SHALL keep exactly one SBOM per format.

#### Scenario: Two platforms, two formats

- **WHEN** a `[linux/amd64, linux/arm64]` rebuild is placed with SBOM formats `spdx-json` and `cyclonedx-json`
- **THEN** the index carries four SBOM referrers, one per format and platform, each annotated with its platform

#### Scenario: One platform's SBOM fails

- **WHEN** generating the `linux/arm64` SBOM fails
- **THEN** the operation fails, as when an SBOM fails today

### Requirement: SBOM coverage is counted per platform

Wherever knock decides whether a rebuilt image's SBOMs are complete (the SBOM backfill of
`reconcile` for a transformed variant, and the arrival check of `promote`), it SHALL require, for
each configured format, one SBOM referrer per platform of the index, matched by
`{prefix}.sbom.platform`. A copied image SHALL keep being counted per format only. An SBOM referrer without that annotation
SHALL count for an image that carries exactly one platform, so that images placed before this change
stay covered. With an empty label prefix, knock SHALL fall back to counting formats only.

#### Scenario: Missing arm64 SBOM is backfilled

- **WHEN** a placed two-platform rebuild carries SBOMs for `linux/amd64` only
- **THEN** reconcile plans an SBOM backfill for that tag

#### Scenario: Older single-platform image stays covered

- **WHEN** a single-platform image placed before this change carries one unannotated SBOM per format
- **THEN** reconcile plans no SBOM backfill for it

#### Scenario: A copied multi-arch index is not re-scanned

- **WHEN** an untransformed import has placed an upstream multi-platform index with one unannotated SBOM per format
- **THEN** reconcile plans no SBOM backfill for it

#### Scenario: Promotion refuses a missing platform SBOM

- **WHEN** `knock promote` copies a staged two-platform rebuild and the destination receives no `linux/arm64` SBOM
- **THEN** the entry is refused with a message naming the missing format and platform, and the tag is not written
