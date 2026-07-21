---
title: "Redis: semver selection"
description: "Semver selection and alias tracking over a real image (redis 7.2.x)."
sidebar_position: 2
---

Shows how `{major}.{minor}` aliases track the highest patch within each minor stream, and `latest` tracks the highest overall. Redis layers are larger than busybox, so the first copy takes a little longer.

```yaml title="docs/examples/redis/redis.yml" file=../../examples/redis/redis.yml
```

Run it: `uv run knock reconcile docs/examples/redis`
