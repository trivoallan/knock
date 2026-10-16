# Retention

Caps *valid, in-selection* tags with `archive: {keep, olderThanDays}`: knock keeps the N most-recently imported tags and marks the older surplus `pending-deletion` (reason `retention-excess`) for the reaper. Retention never hard-deletes — it only ever marks. See [Deletion & retention](../../explanation/deletion-and-retention.md#retention-capping-valid-tags) for the full model.

[`docs/examples/retention/redis.yml`](../../examples/retention/redis.yml)

Run it: `uv run knock reconcile docs/examples/retention`
