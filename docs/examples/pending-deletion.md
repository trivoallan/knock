---
title: "Pending-deletion (soft delete)"
description: "Soft delete: mark dropped tags with a pending-deletion referrer instead of deleting."
sidebar_position: 5
---

When a tag leaves the selection, `deletionMode: mark` attaches a `pending-deletion` OCI referrer instead of deleting it — the image stays pullable until an external reaper (e.g. `houba purge`) acts. Marks auto-clear if the tag re-enters the selection. See [Deletion & retention](../explanation/deletion-and-retention.md) for the full model.

```yaml title="docs/examples/pending-deletion/pending-deletion.yml"
# Demonstrates deletionMode: mark — when a tag leaves the selection, houba attaches a
# pending-deletion OCI referrer instead of deleting it, so an external reaper that can
# see production usage owns the actual purge. The image digest stays immutable and the
# tag stays pullable until the reaper acts. Marks auto-clear if the tag re-enters.
#
# Resolution cascade (most-specific wins):
#   deletionMode on the policy  ← wins (most specific)
#   else destination deletion_mode in HOUBA_REGISTRIES
#   else global HOUBA_DELETION_MODE (default: purge)
#
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata:
  name: redis-delegated
spec:
  artifactType: image
  source:
    registry: docker.io
    repository: library/redis
  deletionMode: mark
  imports:
    - name: v7
      owners:
        - group:default/data-platform     # stamped as io.houba.owners
      tags:
        includeRegex: "^7\\.2\\."
      destinations:
        # `registry` omitted → resolves to the single configured registry ("local").
        - project: demo
          repository: redis-delegated
```

Run it: `uv run houba reconcile docs/examples/pending-deletion`
