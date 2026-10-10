---
title: "Repair rebuild"
description: "Rebuild path that upgrades OS packages from the internal mirror, on an operator-chosen epoch."
sidebar_position: 5
---

The [hardened rebuild](hardened.md) with one more step: once `rewritePackageSources` has pointed the image at the internal mirror, `upgradePackages` upgrades every installed OS package (apt on Debian and Ubuntu, apk on Alpine). It is how a version flagged with a fixable CVE gets repaired without waiting for upstream to republish the tag.

```yaml title="docs/examples/repaired/redis.yml" file=../../examples/repaired/redis.yml
```

Run it: `uv run knock reconcile docs/examples/repaired` — needs `buildctl` on `PATH`, a BuildKit daemon, and `KNOCK_TRANSFORM_PACKAGE_MIRRORS` set.

What to know before you use it:

- **`epoch` is the trigger.** Nothing is rebuilt until you change it. Changing it rebuilds **every tag the import selects**, in one pass, with no stability window. A wide `includeRegex` means a long pass: narrow the selection to the versions you serve.
- **The order is enforced.** `upgradePackages` without `rewritePackageSources` earlier in the same list is a validation error (exit 1, nothing placed), so an upgrade never reaches a public repository.
- **It fails rather than pretend.** An image with neither `apt-get` nor `apk` (rpm-based, distroless) fails the build for that tag, on every pass, until you remove the step or route the import through the copy path. The signed lineage never claims an upgrade that did not happen.
- **The source's user is kept.** A source image that declares a non-root `User` is rebuilt as root and restored to that user. A `User` value that is not a plain `name` or `uid[:gid]` fails the operation (`UnsafeSourceUserError`).
- **Only OS packages are repaired.** The application binary, statically linked helpers and bundled language modules are not touched: on `redis:7.2.0`, every fixable finding on Debian packages goes away, while those on the `redis` binary and on the Go modules of the bundled `gosu` remain. Only a newer upstream image removes them.
- **knock does not judge the result.** The rebuilt image is pushed to the destination as any rebuild is. Evaluate it with your scanner or gate before relying on it. `apt-get upgrade` does not install new dependencies, so a fix that needs one stays unapplied and your scanner will still report it.

Decision record: [ADR 0054 — `upgradePackages`, the repair step](https://github.com/trivoallan/knock/blob/main/docs/architecture/decisions/0054-upgrade-packages-step.md).
