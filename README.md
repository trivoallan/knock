# houba

**OCI image mirroring CLI with policy-driven tag selection.**

`houba` mirrors container images from a public source registry (Docker Hub, Quay, GHCR…) into a private OCI registry (Harbor), applying per-product policies for tag selection, exclusion patterns, semver ordering, archival, and OCI label enrichment.

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org)

---

## What it does

For each product you want to mirror you write a small `properties.yml` describing source/destination, tag filters. `houba` then:

1. Lists tags on the source registry (via `skopeo`).
2. Computes which tags must be imported, updated, or deleted — based on regex include/exclude filters, semver ordering, and a 7-day stability window for digest changes.
3. For each tag to import: pulls the image, builds a small wrapper layer (via `buildctl` / BuildKit) embedding configurable shell scripts and certificates, pushes to your Harbor.
4. Applies OCI labels (`{prefix}.source.registry`, `{prefix}.source.tag`, `{prefix}.import.date` …) — prefix is configurable.
5. Optionally archives obsolete tags rather than deleting them.
6. Sends a Teams webhook notification on success / failure.

The same CLI also offers operational commands: `archive restore`, `archive purge`, `proxycache update`, `product delete`, `product init`.

> **Status:** Phase B (this release, `v0.2.0-phase-b`) ships the foundations + all I/O adapters. The use-cases (`product import`, `archive restore`…) come in Phase C. See [docs/](docs/) for the design and implementation plans.

---

## Quick start

### Install

`houba` is published as a Docker image bundling skopeo, BuildKit (`buildctl`), git, and the Python CLI itself:

```bash
docker pull ghcr.io/<your-org>/houba:v0-rc
```

Or from source with [uv](https://github.com/astral-sh/uv):

```bash
git clone https://github.com/<your-org>/houba.git
cd houba
uv sync
uv run houba --help
```

You still need `skopeo`, `buildctl`, and `git` on `PATH` when running from source.

### Configuration

`houba` reads its configuration from environment variables (12-factor). All variables are namespaced `HOUBA_*`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `HOUBA_HARBOR_URL` | yes | — | Base URL of the Harbor instance (e.g. `https://harbor.example.com`) |
| `HOUBA_HARBOR_USER` | yes | — | Harbor robot account (e.g. `robot$houba`) |
| `HOUBA_HARBOR_PASSWORD` | yes | — | Secret token for the robot account |
| `HOUBA_HARBOR_PROJECT_DEFAULT` | no | — | Default Harbor project when not specified per-product |
| `HOUBA_GITLAB_URL` | yes | — | Base URL of the GitLab instance |
| `HOUBA_GITLAB_TOKEN` | yes | — | Personal access token (read/write API) |
| `HOUBA_GITLAB_GROUP` | yes | — | GitLab group containing per-product repositories |
| `HOUBA_TEAMS_WEBHOOK_URL` | no | — | Disables notifications when absent |
| `HOUBA_LABEL_PREFIX` | no | `io.houba` | OCI label key prefix (e.g. `org.example.mirror`) |
| `HOUBA_LOG_FORMAT` | no | `text` | `text` or `json` |
| `HOUBA_LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `HOUBA_DRY_RUN_TAGS` | no | `false` | Skip image pushes |
| `HOUBA_DRY_RUN_DELETIONS` | no | `false` | Skip deletions |
| `HOUBA_WORK_DIR` | no | `/tmp/houba-work` | Scratch directory for clones/builds |

### Capture production fixtures (development)

To capture a snapshot of an existing Harbor project for use in tests:

```bash
houba dev capture --project <project> --repository <repository> \
  --output tests/fixtures/captured/
```

See [docs/runbooks/capture-fixtures.md](docs/runbooks/capture-fixtures.md).

---

## Architecture

`houba` follows hexagonal architecture (ports & adapters):

```
houba/
├── domain/         pure business logic (semver, properties, tag filter, purge, plan, labels)
├── ports/          typing.Protocol interfaces (harbor, source_registry, image_builder,
│                   git_repo, gitlab, notifier, clock)
├── adapters/       concrete implementations (httpx, subprocess)
├── use_cases/      orchestration (Phase C)
└── cli/            Typer entry points
```

**Golden rules**

- `domain/` never imports I/O (no `httpx`, no `requests`, no `subprocess`).
- `use_cases/` receive ports by constructor injection; they don't import adapters.
- `cli/` does parsing only; everything else is delegated.
- Environment variables are read only inside `houba/config.py`.

This makes the business logic 100% unit-testable with in-memory fakes (`tests/fakes/*`), and the adapters integration-testable in isolation with `respx` (HTTP) or fake-bin shell scripts (CLI tools).

---

## Development

```bash
uv sync                                       # install deps
uv run pytest                                 # full suite
uv run pytest tests/unit/domain --cov-fail-under=90
uv run ruff check . && uv run ruff format --check .
uv run mypy houba
docker build -t houba:dev .                   # build the runtime image
```

Current test coverage: **92.5 % global**, **96 % on `domain/`**.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).

Copyright 2026 Tristan Rivoallan and contributors.
