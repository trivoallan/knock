# Spec Delta

## Purpose

A transform step that upgrades an image's installed OS packages from the internal package mirror during a rebuild, under a human-controlled trigger, so that a version flagged "critical CVE with a fix available" can be repaired by knock instead of waiting for upstream to republish.

## ADDED Requirements

### Requirement: upgradePackages upgrades OS packages through the mirror

A policy transform MAY declare the step `upgradePackages` with one required parameter, `epoch`. When a
variant with this step is rebuilt, the rendered build SHALL upgrade every installed OS package of the
image: through apt on an image that has `apt-get`, through apk on an image that has `apk`. The
upgrade SHALL fetch packages from the repositories the image is configured with at that point of the
build, which `rewritePackageSources` has already pointed at the internal mirror. On apt, the upgrade
SHALL run non-interactively and SHALL include packages held back by phased updates. The build SHALL
leave the image's own package-manager configuration as it found it, apart from the upgraded packages.

#### Scenario: Debian source rebuilt through the mirror

- **WHEN** a policy lists `rewritePackageSources` then `upgradePackages { epoch: "2026-10-10" }` and a selected tag has a Debian or Ubuntu base
- **THEN** the rebuilt image carries the mirror's current versions of its installed packages, and an evaluation of the rebuilt image no longer reports the OS packages the mirror has fixed

#### Scenario: Alpine source rebuilt through the mirror

- **WHEN** the same policy applies to a tag with an Alpine base
- **THEN** the rebuilt image carries the mirror's current apk versions of its installed packages

#### Scenario: Package-manager configuration is restored

- **WHEN** an apt-based image is rebuilt with `upgradePackages`
- **THEN** the rebuilt image's apt configuration files are those of the source, apart from package upgrades; no cache-keeping configuration added for the build remains

### Requirement: The epoch is the trigger and it is a rebuild of every selected tag

`epoch` SHALL take part in the transform version. Changing `epoch` in a policy SHALL make the next
reconcile plan a `rebuild` for every tag the policy selects, with no stability grace period. A
reconcile with an unchanged `epoch` and an unchanged source digest SHALL keep the placed digests.
The rebuilt image's signed transform lineage SHALL record the step with its `epoch`.

#### Scenario: Epoch bump plans a rebuild of every tag

- **WHEN** an operator changes `epoch` on an import that selects twelve tags, then runs `reconcile --plan-out`
- **THEN** the plan holds twelve `rebuild` entries, one per selected tag

#### Scenario: Unchanged epoch keeps everything

- **WHEN** reconcile runs again with the same `epoch` and no upstream digest change
- **THEN** every tag is kept and no build runs

#### Scenario: Lineage records the epoch

- **WHEN** a tag is rebuilt with `upgradePackages { epoch: "2026-10-10" }`
- **THEN** the signed transform attestation lists the step `upgradePackages` with parameter `epoch` equal to `2026-10-10`

### Requirement: Policy validation refuses an upgrade that could bypass the mirror or the vocabulary

Policy validation SHALL refuse a transform list that contains `upgradePackages` without
`rewritePackageSources` earlier in the same list, naming both steps in the error. Validation SHALL
refuse `upgradePackages` without `epoch`, and an `epoch` that is not a string of 1 to 64 characters
drawn from letters, digits, `.`, `_` and `-`. A refused policy SHALL place nothing (exit 1, domain
error), as for any unknown transform step.

#### Scenario: upgradePackages before rewritePackageSources

- **WHEN** a policy lists `upgradePackages` then `rewritePackageSources`
- **THEN** validation fails with an error naming both steps, and nothing is placed

#### Scenario: upgradePackages without rewritePackageSources

- **WHEN** a policy lists `injectCA` then `upgradePackages` and no `rewritePackageSources`
- **THEN** validation fails with an error naming both steps

#### Scenario: Epoch outside the pattern

- **WHEN** a policy declares `epoch: '"; rm -rf /'`, an `epoch` of 65 characters, or omits `epoch`
- **THEN** validation fails and no Dockerfile is rendered

### Requirement: An image that cannot be upgraded fails loudly

When the image has neither `apt-get` nor `apk`, the rebuild SHALL fail with a message naming the
step and the missing package managers. The operation SHALL be reported as failed, nothing SHALL be
pushed for that tag, and the signed lineage SHALL never claim the step was applied.

#### Scenario: Distroless or rpm-based source

- **WHEN** a policy with `upgradePackages` selects a tag whose image has no apt and no apk
- **THEN** the rebuild fails, the operation is reported failed for that tag with the step named, and the destination tag is left as it was

#### Scenario: Failure repeats on every pass

- **WHEN** the same policy runs again unchanged
- **THEN** the same tag fails again; the operator's remedies are to remove the step or to route the import through the copy path
