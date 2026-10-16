# 54. `upgradePackages`, the repair step, applied on order

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

> [!NOTE]
> Revised on 2026-10-16 (change `remediate-on-order`): the step moves from `transform:` to a
> second list, `remediate:`, applied only to an operation the reconcile plan orders remediated,
> and its `epoch` comes with that order instead of the policy. The bullets below say what holds
> now; the first version made a human move `epoch` in the policy and rebuilt every selected tag.

- **A remediation step, `upgradePackages`.** One `RUN` upgrades every installed OS package:
  apt (non-interactive, phased updates included) or apk. On an image with neither, the `RUN`
  exits non-zero with a message naming the step, so the signed lineage never claims an upgrade
  that did not happen.
- **Two lists, and an order is the trigger.** `transform:` (`injectCA`, `rewritePackageSources`,
  `setTimezone`) is applied to every rebuild; `remediate:` (`upgradePackages`,
  `rewritePackageSources`) only to a plan operation carrying `remediate: {epoch}`, which the
  orchestrator adds after judging the source digest (ADR 0051: knock still does not know who
  judges). The step takes no parameter in the policy; the order's epoch is written into the
  `RUN`, so the layer cache cannot serve a previous upgrade. An epoch outside
  `[A-Za-z0-9._-]{1,64}` makes `--apply-plan` refuse the plan file, because it is interpolated
  into a shell command.
- **A copy-only import can be remediated.** With no `transform:`, an ordered operation is built
  from `remediate:` alone; `remediate:` may re-point the package sources itself for that reason.
- **Only a remediation is staged, and it must be.** Under `--stage-to`, an ordered operation is
  held for its own verdict and a transform-only rebuild is placed directly (it is not judged
  again). Without `--stage-to`, an ordered operation is withheld (`remediation-unstaged`); an
  order on an import that declares no `remediate:` is withheld too (`remediation-undeclared`).
- **The remediation does not move the transform version.** The stamp writes
  `io.knock.remediation.steps|epoch` and the predicate an optional `remediation {steps, epoch}`
  beside `steps[]`, so the next pass keeps a remediated image. A rebuild planned onto a remediated
  tag is flagged `remediated: true` in the plan, for the orchestrator to renew the order.
- **The mirror is not optional.** Validation refuses `upgradePackages` unless
  `rewritePackageSources` comes earlier, in the resolved transform or the same remediation list.
  The rule lives in the single validation entry (`validate_transform_steps`); `Registry` stays a
  name-to-compiler map.
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

- A policy declares the repair; it happens on a digest an evaluator refused on a repairable rule,
  once per order, never on its own and never on a whole selection.
- **One rebuild per ordered digest.** The cost follows the refusals, not the selection.
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
- A remediated image is always judged before it is placed: it is held in staging (ADR 0055) and
  `knock promote` places it after a verdict. `--applied-out` reports what each operation became.
- `ImageInfo` gains `user` (default empty) and the regctl adapter reads it from the config it
  already fetches. No new port, adapter, external system or C4 actor: the C4 model is unchanged.
- The `MirrorPolicy` JSON Schema describes both lists; the transform predicate `/v1` gains the
  optional `remediation` field and stays byte-identical for an image no order touched.
- **Breaking for policies.** A knock with this revision refuses `upgradePackages` under
  `transform:` or with an `epoch`; an older knock refuses `remediate:`. Each consumer moves its
  knock pin and its policies in the same change.

- **Verified on order, copy-only, on 2026-10-17** (knock 0.16.0, BuildKit and a `registry:2` in
  uske's kind bench): two imports with no `transform:` and
  `remediate: [rewritePackageSources, upgradePackages]`, `alpine:3.18.0` and `debian:12.0`, were
  planned as copies (`transformed: false`); with `remediate: {epoch}` added to the plan, both were
  built, held in staging, and stamped `io.knock.remediation.steps|epoch` with no
  `io.knock.transform.version`. On the same bench, uske 0.7.0 ordered the repair of two sources
  with a transform: the Alpine one came out sound and was promoted, the Debian `redis:7.2.0` one
  was refused and its source closed.

## Operating it

- **An ordered operation is withheld.** Read its reason in `--applied-out`:
  `remediation-unstaged` means the run had no `--stage-to`; `remediation-undeclared` means the
  import declares no `remediate:`.
- **`upgradePackages: no apt-get or apk in image` on every pass.** The import selects an image the
  step cannot upgrade. Remove the step from that import, or give those tags their own import on
  the copy path.
- **`UnsafeSourceUserError`.** The upstream image declares a `User` knock will not render. Do not
  work around it in the policy: route the image through the copy path and treat the declared
  value as a finding about the source.
- **Rolling back.** Removing `remediate:` from a policy changes nothing already placed: a
  remediated image stays until its source or its transform moves. A knock older than this revision
  refuses `remediate:` (exit 1, nothing placed): put the policies back in the former shape in the
  same change as the downgrade.

Full change: [openspec/changes/upgrade-packages-step](../../../openspec/changes/upgrade-packages-step/proposal.md),
revised by [openspec/changes/remediate-on-order](../../../openspec/changes/remediate-on-order/proposal.md)
([design](../../../openspec/changes/upgrade-packages-step/design.md)).
