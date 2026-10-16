# Reference policy

The reference policy that both `make demo` (the Argo App-of-Apps) and `make local` (the inner-loop overlay) reconcile. One pass demonstrates the **copy path** (busybox) and the **rebuild path** (debian-tz with timezone variants) in a single, self-contained run — no Harbor, no org config required. See the [Getting started](../../tutorials/getting-started.md) tutorial for a guided walkthrough of the copy half.

[`docs/examples/reference/busybox/busybox.yml`](../../examples/reference/busybox/busybox.yml)

[`docs/examples/reference/debian-tz/debian-tz.yml`](../../examples/reference/debian-tz/debian-tz.yml)

Run it: `uv run knock reconcile docs/examples/reference/busybox` (copy path, no extra deps) or `uv run knock reconcile docs/examples/reference/debian-tz` (rebuild path, needs a BuildKit daemon on `PATH`).

---

> [!WARNING]
> **One repository per policy**
>
> Each destination repository must be owned by exactly one `MirrorPolicy` — two policies writing the same repo is rejected at load time (they would mutually delete each other's tags). This is also what makes horizontal sharding safe (one writer per repo).

> [!NOTE]
> Copy-path examples leave `registry` off destinations (resolved to the single configured `local` registry), so they stay portable — the same policy file works against any registry roster.
