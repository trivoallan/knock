---
title: "Retention"
description: "Retention: cap valid in-selection tags by keep-count and age."
sidebar_position: 6
---

Caps *valid, in-selection* tags with `archive: {keep, olderThanDays}`: houba keeps the N most-recently imported tags and marks the older surplus `pending-deletion` (reason `retention-excess`) for the reaper. Retention never hard-deletes — it only ever marks. See [Deletion & retention](../explanation/deletion-and-retention.md#retention-capping-valid-tags) for the full model.

```yaml title="docs/examples/retention/redis.yml" file=./retention/redis.yml
```

Run it: `uv run houba reconcile docs/examples/retention`
