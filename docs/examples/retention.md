---
title: "Retention"
description: "Retention: cap valid in-selection tags by keep-count and age."
sidebar_position: 6
---

Caps *valid, in-selection* tags with `archive: {keep, olderThanDays}`: houba keeps the N most-recently imported tags and marks the older surplus `pending-deletion` (reason `retention-excess`) for the reaper. Retention never hard-deletes — it only ever marks. See [Deletion & retention](../explanation/deletion-and-retention.md#retention-capping-valid-tags) for the full model.

```yaml title="docs/examples/retention/redis.yml"
# Demonstrates the `archive` retention knobs (shipped in v0.5).
# Spec: docs/superpowers/specs/2026-06-14-retention-marking-design.md
#
# Retention is a SECOND source of pending-deletion marks, computed during reconcile:
# among the VALID, in-selection tags of an import, keep the `keep` most-recently-
# imported, and attach a `pending-deletion` referrer (reason=retention-excess) to any
# OLDER one beyond that count that is also older than `olderThanDays`. The usage-gated
# reaper (`houba purge`) then deletes only the marks whose content is unused in prod.
#
# Retention NEVER hard-deletes (even under deletionMode: purge) — it only ever marks,
# so it presupposes a scheduled `houba purge`. Thresholds cascade global (HOUBA_RETENTION)
# <- policy; this policy sets them explicitly. With neither a global default nor `archive:`,
# retention is off and behaviour is unchanged.
#
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata:
  name: redis-retention
spec:
  artifactType: image
  source:
    registry: docker.io
    repository: library/redis
  imports:
    - name: v7
      owners:
        - group:default/data-platform     # stamped as io.houba.owners
      tags:
        includeRegex: "^7\\.2\\."
      archive:
        keep: 3            # always retain the 3 most-recently-imported 7.2.* tags
        olderThanDays: 30  # of the rest, mark only those older than 30 days
      destinations:
        # `registry` omitted → resolves to the single configured registry ("local").
        - project: demo
          repository: redis-retention
```

Run it: `uv run houba reconcile docs/examples/retention`
