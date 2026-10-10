# 54. `upgradePackages`, the repair step

Date: 2026-10-10

## Status

Proposed.

Builds on [51. The gate between reconcile's plan and its application](0051-gate-between-plan-and-apply.md):
a rebuild caused by this step is planned as a `rebuild` and judged on its source digest, with the
limit that ADR names (the rebuilt output is not judged without a closed transit).

## Context

The rebuild path hardens an image (internal CAs, internal package mirrors, timezone) and rebuilds
it on the same base. No step upgrades a package, so a version flagged "critical CVE, fix
available" is not repaired by a rebuild: it stays as it is until upstream republishes the tag.
Organisations that class such a version as *repairable by reconstruction* have no step to declare.

Two shapes were considered: an in-place patch layer from an external tool (Copacetic), and a
fourth transform step. The external tool does not rewrite package repositories (it would fetch
from public repositories on an image knock copied as-is), drops the source's signatures and
referrers, and adds a second build engine. A transform step reuses the mirror the policy already
names, the stamp, the SBOM and the signature of the existing rebuild path.

## Decision

- **A fourth step, `upgradePackages { epoch }`.** One `RUN` upgrades every installed OS package:
  apt (non-interactive, phased updates included) or apk. On an image with neither, the `RUN`
  exits non-zero with a message naming the step, so the signed lineage never claims an upgrade
  that did not happen.
- **`epoch` is the trigger, and a human moves it.** It is a step parameter, so it takes part in
  the transform version: a new epoch plans a rebuild of every tag the import selects, with no
  stability window. It is also written into the `RUN`, so the layer cache cannot serve a previous
  upgrade. `epoch` is 1 to 64 characters of `[A-Za-z0-9._-]`; anything else is refused at
  validation, because it is interpolated into a shell command.
- **The mirror is not optional.** Validation refuses `upgradePackages` unless
  `rewritePackageSources` comes earlier in the same list. The rule lives in the single validation
  entry (`validate_transform_steps`); `Registry` stays a name-to-compiler map.
- **No `# syntax=` directive.** It would make the BuildKit daemon pull the Dockerfile frontend
  from a public registry during a rebuild. The daemon's built-in frontend handles the cache mount.
- **The rebuild path keeps the source's user.** Transform steps write to system paths. When the
  source config declares a non-root `User`, the rendered Dockerfile switches to root and restores
  that user at the end. A root-equivalent source (`""`, `root`, `0`, `0:0`, `root:root`) renders
  byte-for-byte as before, and no existing transform version changes.
- **The source's `User` is untrusted.** It comes from an upstream image and `USER` has no
  quoting. A value that is not a plain `name` or `uid[:gid]` fails the operation with
  `UnsafeSourceUserError` (domain error, exit 1) before anything is rendered. It is refused, never
  sanitised: a rebuilt image must not run as a user its source did not declare.
- **apt downloads are shared across a rebuild wave** through a BuildKit cache mount. The image's
  own `docker-clean` configuration is set aside for the upgrade and restored in the same `RUN`.

## Consequences

- A policy can now declare the repair. It happens when an operator changes `epoch`, never on its
  own.
- **A new epoch costs one rebuild per selected tag, in one pass.** No budget bounds it; the
  import's selection is the lever. Revisit a per-pass budget if a pass exceeds the orchestrator's
  time budget, or if an import selects more than about fifty tags.
- `apt-get upgrade` installs no new dependency: a fix that needs `dist-upgrade` stays unapplied
  and is visible only to whatever evaluates the rebuilt image.
- **Only OS packages are repaired.** What an image carries outside its package manager stays as
  it was: the application binary itself, a statically linked helper, bundled language modules.
  On `redis:7.2.0` the step cleared every fixable finding on Debian packages (230 to 0) and left
  238 fixable findings on the `redis` binary and on the Go modules of its bundled `gosu`. A
  scanner will keep reporting those; only a newer upstream image removes them.
- A base distribution past its end of life cannot be repaired this way: its security
  repositories stop serving packages and the upgrade fails (loudly, nothing is pushed).
- **An unreachable mirror fails the rebuild.** By default `apt-get update` exits 0 when a
  repository cannot be fetched, the upgrade then finds nothing to do, and the build would succeed
  with nothing upgraded. The step runs the update with `APT::Update::Error-Mode=any`, so any
  fetch failure is fatal, including one repository out of several. Debian 10's apt ignores that
  option (Debian 11 and later, and Ubuntu 18.04 and later, honour it), so the step also starts
  from an empty index and requires one after the update. That older-apt guard only
  catches a mirror that serves nothing at all. `apk upgrade --no-cache` already refuses to
  continue on an unavailable repository. Verified with real builds on Debian 10 and 12 and
  Alpine 3.20.
- `rewritePackageSources` points **every** repository the image declares at the mirror host. An
  image that adds a vendor repository next to its distribution's needs the mirror to serve each
  of them under its original path, or the upgrade fails on the missing one.
- rpm-based and distroless images are out of reach of this step (`rewritePackageSources` knows
  apt and apk only). They fail loudly; the copy path remains.
- The rebuilt output is still pushed to the destination without a verdict on it (ADR 0051's
  limit). Turning the repair on for policies that serve production belongs with two-phase
  placement, tracked in `TODOS.md`.
- `ImageInfo` gains `user` (default empty) and the regctl adapter reads it from the config it
  already fetches. No new port, adapter, external system or C4 actor: the C4 model is unchanged.
- The `MirrorPolicy` JSON Schema gains a `oneOf` branch; the transform predicate `/v1` is
  unchanged (the step and its `epoch` appear in `steps[].params`).

## Operating it

- **A pass takes too long after an epoch change.** The wave is one build per selected tag. Narrow
  `includeRegex` (or pin fewer tags), then run again; tags already rebuilt at the new epoch are
  kept.
- **`upgradePackages: no apt-get or apk in image` on every pass.** The import selects an image the
  step cannot upgrade. Remove the step from that import, or give those tags their own import on
  the copy path.
- **`UnsafeSourceUserError`.** The upstream image declares a `User` knock will not render. Do not
  work around it in the policy: route the image through the copy path and treat the declared
  value as a finding about the source.
- **Rolling back.** Removing the step from a policy changes the transform version, so the next
  pass rebuilds the selected tags without the upgrade (one wave). A knock older than this change
  refuses a policy that names the step (`unknown transform step`, exit 1, nothing placed):
  remove the step before downgrading.

Full change: [openspec/changes/upgrade-packages-step](../../../openspec/changes/upgrade-packages-step/proposal.md)
([design](../../../openspec/changes/upgrade-packages-step/design.md)).
