# houba — Design Overview

## What problem this tool solves

Many organisations maintain a private OCI registry that mirrors a curated subset of public images (Docker Hub, Quay, GHCR, …). Doing this by hand is tedious and error-prone:

- Which tags should we mirror? Latest five semver? Anything matching a regex? Anything not in an exclusion list?
- When does a digest change behind a moving tag (e.g. `1.36`) — do we re-pull immediately or wait for the upstream maintainer to settle?
- Once mirrored, how do we record provenance (source registry / repository / tag / digest / import date) for traceability?
- When a product is decommissioned, how do we archive its tags rather than lose them?

`houba` answers all of that with a single, declarative configuration per product and a deterministic CLI.

## Architecture

`houba` is structured as a hexagonal (ports-and-adapters) Python application:

```
┌────────────────────────────────────────────────────────────────┐
│                         CLI (Typer)                            │
│                  parses args, exits with code                  │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│                       Use cases                                │
│      product_import / archive_purge / proxycache_update …      │
│         (receives ports by constructor injection)              │
└──────┬─────────────────────────────────────────────────┬───────┘
       │                                                 │
       ▼                                                 ▼
┌──────────────────┐                            ┌────────────────────┐
│ Domain (pure)    │                            │     Ports          │
│ semver, tag      │                            │ Harbor, source     │
│ filter, purge,   │                            │ registry, builder, │
│ plan, labels,    │                            │ git, gitlab,       │
│ props            │                            │ notifier, clock …  │
└──────────────────┘                            └────────┬───────────┘
                                                         │
                                                         ▼
                                              ┌──────────────────────┐
                                              │      Adapters        │
                                              │ HarborHttp, Skopeo,  │
                                              │ Buildkit, GitCli,    │
                                              │ GitLabHttp, Teams …  │
                                              └──────────────────────┘
```

### Golden rules

1. **`domain/` is pure.** No `httpx`, no `requests`, no `subprocess`, no environment lookups. Pure functions on dataclasses. Coverage target ≥ 90 %.
2. **`use_cases/` get ports by constructor injection.** They orchestrate domain + ports, never importing adapters directly.
3. **`cli/` is thin.** It parses CLI arguments, builds the composition root (`cli/_di.py`), invokes the use case, and maps exceptions to exit codes.
4. **One Groovy function = one Python function.** No giant orchestrators. This makes every step testable in isolation.
5. **Environment variables are read only by `houba/config.py`** (Pydantic Settings). Any other code path that needs config receives it as an explicit parameter.

This separation is what lets the business logic be 100 % unit-testable with in-memory fakes (`tests/fakes/*`) and the adapters integration-testable in isolation with `respx` (HTTP) or fake-bin shell scripts (CLI tools).

## Tag selection — the heart of the tool

Given a product whose source is `docker.io/library/busybox`, the function `compute_tags_to_import` (in `domain/tag_filter.py`) takes:

- The list of tags currently published upstream (e.g. `["1.36", "1.37", "1.36.1", "latest"]`).
- The product `properties.yml` (include regex, exclude regex, semver-only flag, …).
- The current state in the mirror (digests, push dates, labels).
- The current time (injected via a `Clock` port for testability).

It returns three sets:

- `tags_to_import` — present upstream, absent or stale downstream
- `tags_to_update` — present in both, but upstream digest has changed **and the change has been stable for at least 7 days** (avoids mirroring half-pushed images)
- `tags_to_delete` — present downstream, absent upstream beyond the configured retention

This is a pure function. It has dozens of test cases covering all the edge cases. No I/O means no flakiness.

## OCI labels for provenance

Every imported image is enriched with a configurable set of labels:

- `{prefix}.source.registry` — e.g. `docker.io`
- `{prefix}.source.repository` — e.g. `library/busybox`
- `{prefix}.source.tag` — e.g. `1.36`
- `{prefix}.source.digest` — e.g. `sha256:abc…`
- `{prefix}.import.date` — ISO 8601
- `{prefix}.import.harbor` — which Harbor instance received it

The prefix is configurable via `HOUBA_LABEL_PREFIX` (default `io.houba`).

## Error model

```
HoubaError                          (base)
├── DomainError          exit 1     business / validation error
│   ├── PropertiesValidationError
│   └── NoTagsToImportError
├── AdapterError         exit 2     infra / external dependency error
│   ├── HarborError
│   │   ├── HarborAuthError
│   │   ├── HarborNotFoundError
│   │   └── HarborTransientError    (retried 5× before bubbling up)
│   ├── GitError
│   ├── SkopeoError
│   ├── BuildkitError
│   └── GitLabError
├── ConfigError          exit 3     missing or invalid configuration
└── InternalError        exit 4     bug / assertion failure
```

Transient errors (HTTP 5xx, network timeouts) are automatically retried up to 5 times with exponential backoff inside the adapter layer, then bubble up as their parent class if the retry budget is exhausted. No retry logic ever appears in `domain/`.

## Status

- **Phase A (delivered)** — project foundations, complete `domain/` layer with > 90 % coverage, read-only adapters for Harbor / source registry, `houba dev capture` to record production fixtures.
- **Phase B (delivered, this release)** — all 4 missing ports and their adapters: image builder (BuildKit), git CLI, GitLab REST API, Teams webhook. Harbor write-side (delete, tag create/delete, label, immutable rule) added. Composition root wired. Runtime Docker image embeds skopeo + buildctl + git.
- **Phase C (next)** — use cases: `product_import`, `product_init`, `product_delete`, `proxycache_update`, `archive_restore`, `archive_purge`.

See [README](../README.md) for installation and configuration.
