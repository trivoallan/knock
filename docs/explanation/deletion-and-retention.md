---
title: "Deletion & retention"
description: "The two removal axes, and why houba marks (usage-gated) instead of hard-deleting."
sidebar_position: 5
---

houba removes tags along two distinct axes, and **never hard-deletes a tag without it first
passing a usage gate**. This page explains the model; for the runnable steps, see
[Purge unused tags](../how-to/purge-unused-tags.md).

## Delegated deletion (`deletionMode: mark`)

When a tag drops out of the selection, houba does **not** delete it — it attaches a
`pending-deletion` OCI referrer (`application/vnd.houba.lifecycle.pending+json`, carrying
`io.houba.lifecycle.marked-at` / `io.houba.lifecycle.reason` / `io.houba.lifecycle.state` and the
policy/import identity). The digest is unchanged and the tag stays pullable. An external reaper
lists these referrers, checks production usage, and purges. If the tag re-enters the selection on
a later run, houba clears the mark. If `deletionMode` is later removed or changed to `purge`, the
next reconcile hard-deletes any still-undesired tags (the stale marks become moot).

Resolution is a cascade (most-specific wins): `deletionMode` on the policy wins, else the
destination's `deletion_mode` (in `HOUBA_REGISTRIES`), else the global `HOUBA_DELETION_MODE`
(default `purge`).

*Example:* [`pending-deletion/pending-deletion.yml`](../examples/pending-deletion/pending-deletion.yml).

## Retention (capping valid tags)

Delegated deletion handles tags that *fall out of selection*. **Retention** handles the opposite
problem: tags that stay perfectly *valid* but pile up forever — a policy that mirrors every patch
(`includeRegex: "^7\\.2\\."`) keeps accumulating `7.2.z` tags, each still in selection, so the
selection axis never touches them.

[`retention/redis.yml`](../examples/retention/redis.yml) activates the `archive` knobs to cap them:

```yaml
archive:
  keep: 3            # always retain the 3 most-recently-imported 7.2.* tags
  olderThanDays: 30  # of the rest, mark only those older than 30 days
```

During `reconcile`, houba ranks each stream's in-selection tags by **import time** (houba's own
stamp, `org.opencontainers.image.created`), keeps the `keep` newest, and attaches a
`pending-deletion` referrer (reason `retention-excess`) to any older tag beyond that count — both
conditions must hold (`keep` **and** `olderThanDays`). Alias targets (e.g. whatever `latest` points
at) are never marked, and a mark clears automatically if the tag stops being excess on a later run.

:::warning
Retention **only ever marks** — it never hard-deletes, even under `deletionMode: purge`: removing a *valid* tag must always pass the usage gate. So retention presupposes a scheduled [**`houba purge`**](../how-to/purge-unused-tags.md); without one, marks accumulate harmlessly and the tags stay fully pullable.
:::

Thresholds cascade **global ← policy**, per field: a fleet-wide default in `HOUBA_RETENTION`
(a JSON `Archive` object) is refined by a policy's `archive:`. With neither set, retention is off
and behaviour is unchanged.

```bash
# fleet-wide default (optional); a policy's `archive:` overrides it per field
export HOUBA_RETENTION='{"keep": 5, "olderThanDays": 90}'
```
