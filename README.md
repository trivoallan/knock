# houba

**The single front door for the external container images your organization runs.**

> **Status — early development.** Foundations and I/O adapters are in place (`v0.2`); the derive-and-stamp engine and the provenance schema are the current focus ([roadmap](docs/roadmap.md)). Not yet production-ready.

Every public image that enters your registry passes through houba: it is rebuilt with your hardening policy — internal CA certificates, internal package mirrors — and stamped with **standardized, portable provenance** (OCI annotations + SLSA attestations).

The payoff lands the morning a critical CVE drops. Because every running image carries a consistent provenance stamp, *"what's our blast radius, and who owns it?"* becomes **one query** in the observability stack you already have — not a frantic spreadsheet. houba produces the stamp; your tools (Datadog, PowerBI, Wiz…) read it.

houba is **not** an image mirror. `skopeo sync` and Harbor replication copy images byte-for-byte. houba *transforms* them and makes them *traceable*.

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org)

---

## How it works

For each image you bring in, you declare a small policy (source, tag-selection rules, hardening steps). houba then:

1. Lists tags on the source registry (via `skopeo`).
2. Selects which tags to derive — regex include/exclude filters, semver ordering, a 7-day stability window for moving digests.
3. Rebuilds each selected image through your hardening policy (via `buildctl` / BuildKit): internal CA certificates, internal package mirrors, configurable steps.
4. Stamps the result with standardized provenance (OCI annotations today; SLSA attestations on the roadmap).
5. Pushes the derived image to your registry, optionally archiving superseded tags.
6. Notifies on success / failure (Teams webhook).

See the [roadmap](docs/roadmap.md) for what is built versus planned, and the [design overview](docs/design.md) for the architecture.

### Run it as a deployment

A **reference deployment** runs houba as a Kubernetes CronJob (git-sync'd policies, rootless
buildkitd, a blast-radius consumer) — the same `deploy/` manifests serve a local kind demo and a
production blueprint. Fastest taste:

```bash
make demo-lite        # kind up, reconcile the busybox example, print blast radius
```

See [docs/runbooks/reference-deployment.md](docs/runbooks/reference-deployment.md).

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
| `HOUBA_MAX_CONCURRENCY` | no | `4` | Max parallel tag operations per run (`1` = sequential). Override per run with `--concurrency`/`-j`. |
| `HOUBA_REGISTRIES` | no | `{}` | JSON map of logical registry names to `RegistryConfig` objects (see below) |

**`RegistryConfig` fields** (each entry in `HOUBA_REGISTRIES`):

| Field | Required | Description |
|---|---|---|
| `host` | yes | Registry host, e.g. `harbor.example.com` or `localhost:5001` |
| `username` | no | Registry username (must be set together with `password`) |
| `password` | no | Registry password (must be set together with `username`) |
| `tls_verify` | no | Set to `false` for plain-HTTP registries (default `true`); houba runs `regctl registry set … --tls disabled` automatically |
| `ca_cert` | no | Path to a CA PEM regctl should trust for this registry's TLS (for registries behind an internal CA). |

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
