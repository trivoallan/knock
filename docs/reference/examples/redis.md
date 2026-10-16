# Redis: semver selection

Shows how `{major}.{minor}` aliases track the highest patch within each minor stream, and `latest` tracks the highest overall. Redis layers are larger than busybox, so the first copy takes a little longer.

[`docs/examples/redis/redis.yml`](../../examples/redis/redis.yml)

Run it: `uv run knock reconcile docs/examples/redis`
