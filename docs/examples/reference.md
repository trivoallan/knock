---
title: "Reference policy"
description: "The reference policy the demo reconciles: copy (busybox) and rebuild (debian-tz) in one self-contained pass."
sidebar_position: 1
---

The reference policy that both `make demo` (the Argo App-of-Apps) and `make local` (the inner-loop overlay) reconcile. One pass demonstrates the **copy path** (busybox) and the **rebuild path** (debian-tz with timezone variants) in a single, self-contained run — no Harbor, no org config required. See the [Getting started](../tutorials/getting-started.md) tutorial for a guided walkthrough of the copy half.

```yaml title="docs/examples/reference/busybox/busybox.yml"
# Smallest end-to-end example: mirror a few busybox tags into a local registry,
# with derived moving-tag aliases. busybox is tiny, so the copy is fast.
#
#   uv run houba reconcile docs/examples/reference/busybox --dry-run
#   uv run houba reconcile docs/examples/reference/busybox
#
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata:
  name: busybox
spec:
  artifactType: image
  source:
    registry: docker.io
    repository: library/busybox
  imports:
    - name: stable
      owners:
        - group:default/platform     # stamped (comma-joined) as io.houba.owners
      tags:
        # Anchored to plain major.minor.patch ($): the -glibc/-musl/-uclibc image
        # variants parse as semver pre-releases, so without the anchor they leak in.
        includeRegex: "^1\\.3[78]\\.\\d+$"   # the 1.37.x and 1.38.x families
        aliases:
          - "{major}.{minor}"           # 1.37 → highest 1.37.z, 1.38 → highest 1.38.z
          - "latest"                    # → highest overall
      destinations:
        # `registry` omitted → resolves to the single configured registry ("local").
        - project: demo
          repository: busybox
```

```yaml title="docs/examples/reference/debian-tz/debian-tz.yml"
# Rebuild path, runnable self-contained (no Harbor, no org config): rebuild debian
# through the transform engine and fan ONE source tag into two regional variants via
# the per-variant `suffix`. setTimezone is the only built-in step needing no org config.
#
# In-cluster:  make demo / make local (the debian-tz half of the reference policy)
# Locally (needs a BuildKit daemon on PATH):
#   uv run houba reconcile docs/examples/reference/debian-tz
#
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata:
  name: debian-tz
spec:
  artifactType: image
  defaults:
    vendor: Example Platform Team    # stamped as org.opencontainers.image.vendor (the rebuilder)
    owners:
      - group:default/platform       # default owner for every import...
  source:
    registry: docker.io
    repository: library/debian
  imports:
    - name: slim
      owners:
        - group:default/platform     # ...overridable per import (here: co-owned)
        - group:default/base-images
      tags:
        semverOnly: false     # bookworm-slim is not a semver tag
        includeRegex: "^bookworm-slim$"
      variants:
        - name: eu
          suffix: "-eu"
          transform:
            - setTimezone: { zone: Europe/Paris }
        - name: us
          suffix: "-us"
          transform:
            - setTimezone: { zone: America/New_York }
      destinations:
        # `registry` omitted → resolves to the single configured registry ("local").
        - project: demo
          repository: debian
```

Run it: `uv run houba reconcile docs/examples/reference/busybox` (copy path, no extra deps) or `uv run houba reconcile docs/examples/reference/debian-tz` (rebuild path, needs a BuildKit daemon on `PATH`).

---

**One repository per policy.** Each destination repository must be owned by exactly one `MirrorPolicy` — two policies writing the same repo is rejected at load time (they would mutually delete each other's tags). This is also what makes horizontal sharding safe (one writer per repo).

**Copy-path examples leave `registry` off destinations** (resolved to the single configured `local` registry), so they stay portable — the same policy file works against any registry roster.
