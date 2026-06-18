---
title: "Pending-deletion (soft delete)"
description: "Soft delete: mark dropped tags with a pending-deletion referrer instead of deleting."
sidebar_position: 5
---

When a tag leaves the selection, `deletionMode: mark` attaches a `pending-deletion` OCI referrer instead of deleting it — the image stays pullable until an external reaper (e.g. `houba purge`) acts. Marks auto-clear if the tag re-enters the selection. See [Deletion & retention](../../explanation/deletion-and-retention.md) for the full model.

```yaml title="docs/examples/pending-deletion/pending-deletion.yml" file=../../examples/pending-deletion/pending-deletion.yml
```

Run it: `uv run houba reconcile docs/examples/pending-deletion`
