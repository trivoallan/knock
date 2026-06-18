---
title: "Reference policy"
description: "The reference policy the demo reconciles: copy (busybox) and rebuild (debian-tz) in one self-contained pass."
sidebar_position: 1
---

The reference policy that both `make demo` (the Argo App-of-Apps) and `make local` (the inner-loop overlay) reconcile. One pass demonstrates the **copy path** (busybox) and the **rebuild path** (debian-tz with timezone variants) in a single, self-contained run — no Harbor, no org config required. See the [Getting started](../tutorials/getting-started.md) tutorial for a guided walkthrough of the copy half.

```yaml title="docs/examples/reference/busybox/busybox.yml" file=./reference/busybox/busybox.yml
```

```yaml title="docs/examples/reference/debian-tz/debian-tz.yml" file=./reference/debian-tz/debian-tz.yml
```

Run it: `uv run houba reconcile docs/examples/reference/busybox` (copy path, no extra deps) or `uv run houba reconcile docs/examples/reference/debian-tz` (rebuild path, needs a BuildKit daemon on `PATH`).

---

**One repository per policy.** Each destination repository must be owned by exactly one `MirrorPolicy` — two policies writing the same repo is rejected at load time (they would mutually delete each other's tags). This is also what makes horizontal sharding safe (one writer per repo).

**Copy-path examples leave `registry` off destinations** (resolved to the single configured `local` registry), so they stay portable — the same policy file works against any registry roster.
