# Design

## Context

See `proposal.md` for motivation. The relevant existing pieces:

- The transform engine is a closed vocabulary of pure compilers (`knock/domain/transforms/`): each
  step turns validated params plus resolved resources into Dockerfile lines (`Fragment`); `render()`
  assembles `FROM <source@digest>` plus every fragment in policy order; `transform_version()` hashes
  step names, params and resolved resource data (cert content, mirror URLs), not the rendered text.
- `validate_transform_steps()` in `render.py` is the only validation entry, called once by the
  planner; `Registry` is a plain name-to-compiler map.
- `reconcile_variant()` plans `update` as soon as the recorded transform version differs from the
  policy's, with no grace, per selected tag; the gate (`reconcile-gate`) plans these as `rebuild`.
- `RegctlAdapter.inspect()` already fetches the OCI config (`regctl image config`) for labels;
  `ImageInfo` is a frozen dataclass with defaulted fields; `FakeImageBuilder` journals rendered
  Dockerfiles, so use-case tests see the exact text.
- `rewritePackageSources` rewrites apt and apk sources only (no dnf/zypper); official Debian and
  Ubuntu images ship `apt.conf.d/docker-clean`, which deletes downloaded `.deb` files after install.
- knock's image embeds `buildctl` (the client); `buildkitd` is a separate deployment reached through
  `--addr`, and the Dockerfile frontend that interprets `RUN --mount` is the daemon's.

Constraints from the dossier this repository serves: mirrors only during a rebuild (IF-05), a human
decides when to repair (D-12), everything attested is signed and true (D-28), the rebuilt bytes are
judged before placement only once two-phase placement exists (D-32, not built).

## Goals / Non-Goals

**Goals:**
- Add the repair verb as one more pure compiler, with validation in the existing entry point and
  no new abstraction in `Registry`.
- Keep every existing policy byte-identical and its transform version unchanged.
- Treat the source image as untrusted at both new trust boundaries (`epoch` from the policy,
  `User` from the image).

**Non-Goals:**
- Two-phase placement / staging: a separate design (`TODOS.md`); this change delivers code verified
  locally, and the dossier's guard keeps the step out of production policies until then.
- A Copacetic adapter, `verify --require repaired-since`, automatic epoch bumps, multi-arch, any
  budget on the rebuild wave.

## Decisions

### D1. The epoch is a step parameter, hashed by `transform_version`

The human trigger is `epoch`, a param of the step. Because `transform_version` already hashes step
params, a new epoch changes the version and `reconcile_variant` plans a rebuild of every selected
tag with no extra code. The epoch marker is also written into the `RUN` text so BuildKit's layer
cache cannot serve the previous upgrade.

*Alternatives:* a `--rebuild-all` CLI flag (bypasses the policy, no lineage of why); hashing the
mirror state or the date into the version (rebuilds without a human decision, against D-12); a
BuildKit `--no-cache` for the whole build (throws away the CA and sources layers too).

### D2. One `RUN`, with the apt branch, the apk branch and an explicit failure

The fragment is a single `RUN --mount=type=cache,target=/var/cache/apt,sharing=locked` whose shell
body is built from a list of parts (as `RewritePackageSources` does): the epoch marker; the apt
branch (`DEBIAN_FRONTEND=noninteractive`, move `docker-clean` aside and add a keep-cache snippet,
`apt-get update && apt-get -o APT::Get::Always-Include-Phased-Updates=true -y upgrade`, remove the
snippet and move `docker-clean` back, clean `/var/lib/apt/lists`); the apk branch
(`apk upgrade --no-cache`); `else` an error message naming the step and `exit 1`.

*Why one `RUN`:* `update` and `upgrade` must share a layer for cache busting; the cache mount and
the `docker-clean` dance must bracket the upgrade in the same shell; one instruction keeps the
fragment shaped like the other steps. *Why `exit 1`:* the vocabulary is closed; a signed lineage
must never say "upgraded" when nothing was. *Why phased updates:* Ubuntu otherwise skips a fix
silently; the option is inert on Debian and Alpine. *Why no `# syntax=` directive:* it would make
`buildkitd` pull the frontend image from Docker Hub during a rebuild (IF-05); the daemon's built-in
frontend handles `RUN --mount`, and task 1.1 checks the deployed daemon's version instead.

### D3. The ordering rule lives in `validate_transform_steps`

`upgradePackages` requires `rewritePackageSources` earlier in the same list. The rule compares
indices in `validate_transform_steps` and names both steps in the `PolicyValidationError`.

*Alternative:* a `requires_before` declaration on the compiler and a constraint API on `Registry`.
Rejected for now: one rule, one validation entry; promote to a declaration when a second
inter-step rule appears (recorded as debt).

### D4. Source user: read it, validate it, wrap only when needed

`ImageInfo` gains `user: str = ""` so every existing constructor call and fake stays valid;
`RegctlAdapter.inspect` reads `config.User` from the JSON it already fetches. `render()` gains
`source_user: str = ""`. When the value is root-equivalent, nothing is emitted, which keeps the
byte-identical and transform-version contracts. Otherwise the value must match
`^[A-Za-z0-9._-]{1,64}(:[A-Za-z0-9._-]{1,64})?$`, or `UnsafeSourceUserError` (a `DomainError`,
exit 1 class) is raised before rendering; `_do_import` already turns it into a failed operation.
Within the pattern, `render()` emits `USER root` after `FROM` and `USER <value>` after the last
fragment.

*Alternatives:* sanitising the value (ships an image whose identity is not the source's, against
D-28); trusting it (Dockerfile injection from an untrusted image); handling `USER` inside the
`upgradePackages` fragment only (leaves `injectCA` and `rewritePackageSources` broken on non-root
sources, which is the latent bug this fixes once for all three).

### D5. The rebuild wave is accepted, with the selection as the lever

An epoch change rebuilds every selected tag in one pass, like the initial import does. No budget is
added. The ADR documents the cost and names the policy's selection (`includeRegex`) as the lever.
Escalation trigger, written in the ADR: a pass exceeding the orchestrator's time budget, or an
import selecting more than about fifty tags, reopens a per-pass budget.

### D6. What is not judged, and what guards it

A rebuilt image is pushed to the destination without a verdict on its output, as today. This change
does not alter that; production activation of the step waits for two-phase placement, and the
dossier repository adds a check refusing `upgradePackages` in its policies until then. knock's
example policy uses a public image and never names an organisation.

## Risks / Trade-offs

- [The deployed `buildkitd` is too old for `RUN --mount`] → task 1.1 reads the daemon version in
  `deploy/overlays/local` and the production target before any fragment is written; the only remedy
  is upgrading the daemon, never a `# syntax=` directive.
- [The mirror lacks the `-security` suites or lags upstream] → `apt-get update` fails loudly
  (`BuildkitError`, operation failed, nothing pushed); the dossier's measurement step records the
  mirror's package versions beforehand.
- [A fix needs `dist-upgrade` (new dependency)] → `upgrade` leaves it; the evaluation of the rebuilt
  image still reports the CVE, visible at the verdict rather than at the build; documented limit.
- [Wide selections rebuild hundreds of tags per epoch] → D5; the selection is the lever.
- [`_do_import` catches `Exception`] → pre-existing; a bug in the new code would surface as a failed
  operation rather than a traceback; recorded as debt, not changed here.
- [A legitimate image with an exotic `User`] → refused with the value named; the operator routes it
  through the copy path.

## Migration Plan

1. Ship knock with the step in its vocabulary (release-please). Policies that do not use it render
   byte-identically; `reconcile --plan-out` on the existing policies must plan `keep` everywhere
   (the production smoke test).
2. Only then may a policy declare `upgradePackages`; an older knock refuses such a policy as an
   unknown step (exit 1, nothing placed), which is the rollback signal if knock is downgraded.
3. Rollback of the step itself: remove it from the policy; the transform version changes, so the next
   pass rebuilds the selected tags without the upgrade (one wave).
4. Production activation waits for two-phase placement (separate design).

## Open Questions

- Resolved in task 1.1: the local overlay deploys `moby/buildkit:v0.30.0-rootless`
  (`deploy/components/buildkitd/deployment.yaml`), whose built-in Dockerfile frontend accepts
  `RUN --mount=type=cache` without a `# syntax=` directive. The production target reuses the same
  component; a production manifest pinning an older daemon would have to be raised before enabling
  the step there.
