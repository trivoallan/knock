# Spec: rename houba → knock (clean break)

Status: **Draft**
Date: 2026-07-05

## Summary

Rename the project from **houba** to **knock** — package, CLI, env prefix, OCI contracts,
documentation, deploy manifests, and the GitHub repository. This is a **clean break** (no
backward-compatibility shim), justified by pre-1.0 semver status. Ships as a single coordinated
change on a dedicated branch, landed as one merge into `main`, tagged `0.9.0`.

## Why "knock"

Short, memorable, CLI-friendly (`knock reconcile`, `knock attach`, `knock audit`). Evocative of the
product thesis: knock is the single front door — every external image knocks before it enters.

## Problem & context

The name `houba` carries no meaning in English; it causes confusion in conversation ("what's a
houba?"), is hard to search for, and collides with unrelated results. The project is at 0.x —
semver does not guarantee stability yet, so a clean break costs existing users a config migration
but no API-contract violation. The alternative (a compatibility layer that accepts both old and
new names) would double the surface area indefinitely and add cognitive overhead for a community
that doesn't exist at scale yet.

## Decision

**Clean break. No backward-compatibility shim.** Every `houba` ↦ `knock` and `HOUBA` ↦ `KNOCK`
in code, config, docs, deploy, and published contracts. A single `MIGRATION.md` documents the
upgrade path.

## Premises

1. The project is 0.x (pre-1.0); no semver stability guarantee applies.
2. There is no large external user base that would be disrupted by a breaking rename.
3. A shim (`HOUBA_*` env vars accepted alongside `KNOCK_*`) would create permanent dual naming
   in docs, error messages, and OCI contracts — net negative for clarity.
4. The OCI annotation prefix (`io.houba.*`) is already configurable via `HOUBA_LABEL_PREFIX`
   (soon `KNOCK_LABEL_PREFIX`); existing images keep their stamped annotations untouched — the
   rename changes only what **new** images receive.
5. The predicate URIs (`https://houba.dev/predicate/*/v1`) and artifact types
   (`application/vnd.houba.*`) are stamped on existing attestations and referrers in registries.
   These are **frozen** — verification of already-signed attestations must not break. New images
   get the new URIs; the verifier must accept both until the old cohort ages out.

## Scope

### In scope (the rename itself)

Everything below ships in **one branch, one merge, one tag**.

#### 1. Python package

| What | From | To |
|---|---|---|
| Package directory | `houba/` | `knock/` |
| All `import houba` / `from houba` | `houba` | `knock` |
| `pyproject.toml` name | `houba` | `knock` |
| Script entry point | `houba = "houba.cli.main:_run"` | `knock = "knock.cli.main:_run"` |
| `setuptools.packages` | `["houba"]` | `["knock"]` |
| Error root class | `HoubaError` | `KnockError` |
| Typer app name | `name="houba"` | `name="knock"` |
| `importlib.metadata.version("houba")` | `"houba"` | `"knock"` |

~421 import statements across ~149 files. Mechanical find/replace.

#### 2. Environment variables

| What | From | To |
|---|---|---|
| Pydantic Settings prefix | `env_prefix="HOUBA_"` | `env_prefix="KNOCK_"` |
| All env var references | `HOUBA_*` | `KNOCK_*` |

~474 occurrences across ~129 files. Key vars: `KNOCK_REGISTRIES`, `KNOCK_LABEL_PREFIX`,
`KNOCK_LOG_FORMAT`, `KNOCK_LOG_LEVEL`, `KNOCK_DRY_RUN_TAGS`, `KNOCK_DRY_RUN_DELETIONS`,
`KNOCK_BUILD_PLATFORM`, `KNOCK_WORK_DIR`, `KNOCK_SBOM_FORMATS`, `KNOCK_SCAN_REDIS`,
`KNOCK_ATTEST_SIGNER`, `KNOCK_ATTEST_KEY_REF`, `KNOCK_USAGE_ORACLE_CMD`,
`KNOCK_TRANSFORM_CA_CERTS`, `KNOCK_TRANSFORM_PACKAGE_MIRRORS`.

#### 3. OCI contracts (the sensitive part)

| Contract | Old value | New value | Migration |
|---|---|---|---|
| Annotation prefix default | `io.houba` | `io.knock` | Existing images keep `io.houba.*`; new images get `io.knock.*`. Queries must include both during transition. |
| Artifact type (scan) | `application/vnd.houba.scan.result.v1` | `application/vnd.knock.scan.result.v1` | `gc` must recognize both types when collecting old referrers. |
| Artifact type (lifecycle) | `application/vnd.houba.lifecycle.pending+json` | `application/vnd.knock.lifecycle.pending+json` | `purge` must recognize both when scanning for pending-deletion markers. |
| Predicate URI (transform) | `https://houba.dev/predicate/transform/v1` | `https://knock.dev/predicate/transform/v1` | Cosign verify policies must accept both predicateTypes. |
| Predicate URI (scan) | `https://houba.dev/predicate/scan/v1` | `https://knock.dev/predicate/scan/v1` | Same as above. |
| Redis stream keys | `houba:scan:*` | `knock:scan:*` | One-time rename (or fresh streams). |

**Dual-recognition rule:** `gc`, `purge`, and `audit` must accept **both** old and new artifact
types / annotation prefixes when **reading** (the old cohort ages out over weeks/months). They
only **write** the new values. This is NOT a backward-compat shim for the env/config surface — it
is a data-plane read concern for artifacts already in registries.

Implementation: define `LEGACY_` constants alongside the new ones in `domain/scan/constants.py`,
`domain/lifecycle.py`, and `domain/attestation.py`; the read paths (`gc`, `purge`, `audit`) match
on `{current, legacy}` sets; the write paths use only the current constants. The legacy constants
are removed in the **next** minor release once the old cohort is confirmed aged out.

#### 4. Config defaults

| What | From | To |
|---|---|---|
| `Settings.label_prefix` default | `"io.houba"` | `"io.knock"` |
| `ScanRedisConfig` stream defaults | `"houba:scan:*"` | `"knock:scan:*"` |
| `Settings` work dir default | `"/tmp/houba-work"` | `"/tmp/knock-work"` |

#### 5. Error hierarchy

| Class | From | To |
|---|---|---|
| Root | `HoubaError` | `KnockError` |
| Exit-code map dict | `dict[type[HoubaError], int]` | `dict[type[KnockError], int]` |

The subclasses (`DomainError`, `AdapterError`, `ConfigError`, `InternalError`) and leaves
(`PolicyValidationError`, `RegctlError`, etc.) keep their names — only the root changes.

#### 6. Documentation (~1,959 occurrences across ~133 .md files)

Bulk find/replace with manual proofreading for:
- Prose flow ("houba is..." → "knock is...")
- CLI examples (`houba reconcile` → `knock reconcile`)
- Env var examples (`HOUBA_REGISTRIES=...` → `KNOCK_REGISTRIES=...`)
- OCI annotation examples (`io.houba.policy` → `io.knock.policy`)
- URLs (`github.com/trivoallan/houba` → TBD)
- Predicate URIs and artifact types in examples

#### 7. Tests (~690 occurrences across ~110 files)

- All `import houba` → `import knock`.
- Env var fixtures `HOUBA_*` → `KNOCK_*`.
- Fake-bin scripts: update artifact types and annotation keys.
- **Add transition tests**: `gc` and `purge` must handle referrers / markers that use the old
  `vnd.houba.*` types alongside the new `vnd.knock.*` ones.

#### 8. Deploy / Kubernetes

| What | From | To |
|---|---|---|
| Namespace | `houba` | `knock` |
| K8s resource names | `houba-reconcile`, `houba-gc`, etc. | `knock-reconcile`, `knock-gc`, etc. |
| GHCR image | `ghcr.io/.../houba` | `ghcr.io/.../knock` |
| Docker image tags | `houba:dev`, `houba:ci-*` | `knock:dev`, `knock:ci-*` |
| Makefile cluster | `houba-demo` | `knock-demo` |
| ArgoCD app | `houba.yaml` | `knock.yaml` |
| Secret names | `houba-registries`, `houba-docker-config` | `knock-registries`, `knock-docker-config` |
| Vault/Bao paths | `secret/houba/*` | `secret/knock/*` |

#### 9. CI / Release

| File | Changes |
|---|---|
| `.github/workflows/ci.yml` | `mypy knock`, `--cov=knock`, image tag `knock:ci-*` |
| `.github/workflows/release-please.yml` | GHCR image `knock` |
| `.github/workflows/demo-mongobleed.yml` | Image + cluster name |
| `.github/settings.yml` | Repo name |
| `.gitlab-ci.yml` | Image + env vars |
| `release-please-config.json` | `"package-name": "knock"` |

#### 10. Architecture model

| File | Changes |
|---|---|
| `docs/architecture/workspace.dsl` | ~65 occurrences: system/container/component names, descriptions |
| `docs/architecture/_export/*.mmd` | Regenerate from DSL |
| ADR filenames with "houba" | Rename (3 files) |

#### 11. Website

| File | Changes |
|---|---|
| `website/docusaurus.config.ts` | Title, projectName, baseUrl → `/knock/` |
| `website/package.json` | `"knock-docs"` |
| `website/static/img/social-card.svg` | Text element |

#### 12. Meta-files

| File | Changes |
|---|---|
| `CLAUDE.md` | Full rewrite of all references |
| `README.md` | Full rewrite |
| `CHANGELOG.md` | Add rename notice at top; historical entries stay as-is |

### Out of scope

- **GitHub repository rename** (`trivoallan/houba` → `trivoallan/knock`). Done manually by the
  repo owner after the code rename merges. GitHub's redirect handles old URLs.
- **PyPI package name reservation.** Done manually; the first `0.9.0` publish claims `knock`.
- **Domain registration** (`knock.dev`). Not required for launch — the predicate URI needn't
  resolve (same convention as SLSA with `slsa.dev`). Register opportunistically.
- **Historical changelog rewriting.** `CHANGELOG.md` keeps old entries referencing `houba`;
  a notice at the top explains the rename.
- **regis sibling rename.** `regis` is a separate tool; its rename (if any) is a separate spec.

## Execution plan

The rename is mechanical but high-volume (~3,536 occurrences, 391 files). Execution order
matters to keep the repo buildable at each step.

### Phase 1: Preparation (no code changes yet)

1. **Secure the `knock` PyPI name.** Publish a placeholder `0.0.0` or confirm availability.
2. **Draft `MIGRATION.md`.** Document env var mapping, OCI contract changes, and the
   dual-recognition window for existing artifacts.
3. **Register `knock.dev` domain** (opportunistic; not blocking).

### Phase 2: Code rename (one branch, atomic)

Execute in this order to keep the test suite green at each commit:

1. **Rename the package directory** `houba/` → `knock/`.
2. **Bulk-replace imports and references** in all `.py` files (`houba` → `knock`,
   `HOUBA` → `KNOCK`, `HoubaError` → `KnockError`).
3. **Update `pyproject.toml`** (name, entry point, tool sections).
4. **Run `uv lock`** to regenerate `uv.lock`.
5. **Run the full test suite** (`uv run pytest`) — must be green.
6. **Run `uv run mypy knock`** — must pass.
7. **Run `uv run ruff check . && uv run ruff format .`** — must be clean.

### Phase 3: OCI contracts + dual recognition

1. **Define `LEGACY_*` constants** for old artifact types and predicate URIs.
2. **Update read paths** in `gc`, `purge`, `audit` to match on `{current, legacy}` sets.
3. **Update write paths** to emit only new constants.
4. **Add transition tests** (old-type referrers recognized by new code).

### Phase 4: Documentation, deploy, CI, architecture

1. **Bulk-replace in `.md` files** with manual proofreading pass.
2. **Update deploy manifests** (namespace, resource names, secrets, images).
3. **Update CI workflows.**
4. **Update `workspace.dsl`** and regenerate Mermaid exports.
5. **Update `CLAUDE.md`, `README.md`.**
6. **Run `make reference`** to regenerate docs/reference/ from renamed models.

### Phase 5: Ship

1. **Final full-suite run** (tests + mypy + ruff + coverage gates).
2. **Tag `0.9.0`.**
3. **Merge to `main`.**
4. **Repo owner renames GitHub repo** (`trivoallan/houba` → `trivoallan/knock`).
5. **Publish to PyPI** as `knock 0.9.0`.
6. **Publish GHCR image** as `ghcr.io/.../knock:0.9.0`.

## Risks

| Risk | Mitigation |
|---|---|
| Existing deployments break on env var rename | `MIGRATION.md` + `0.9.0` release notes. No shim — clean break is the point. |
| Old attestations fail cosign verify after predicate URI change | Old attestations keep their old URIs; verify policies must list both. Documented in `MIGRATION.md`. |
| `gc` / `purge` miss old-format referrers | Dual-recognition constants (Phase 3); transition tests enforce this. |
| Search engines / docs links break | GitHub redirect for repo; `CHANGELOG.md` notice; 301 on docs site if custom domain moves. |
| `knock` name collision (PyPI, other projects) | Check PyPI availability before starting. |
| Large diff is hard to review | The rename is mechanical; review the OCI dual-recognition logic (Phase 3) carefully; the rest is `sed`. |

## Decisions ratified

1. **Clean break, no env-var shim.** Accepting old `HOUBA_*` vars alongside `KNOCK_*` would
   create permanent dual naming. Pre-1.0 semver allows the break.
2. **Dual recognition for OCI artifacts is data-plane, not config-plane.** `gc`/`purge`/`audit`
   read both old and new artifact types from registries (where old data lives); they do not
   accept both env prefixes.
3. **Legacy constants removed in next minor.** The dual-recognition window is one release cycle;
   the next minor (0.10.0 or 1.0.0) drops the `LEGACY_*` constants and recognizes only
   `vnd.knock.*`.
4. **Version bump to 0.9.0.** The rename is a significant breaking change; it gets its own minor.
5. **CHANGELOG history is not rewritten.** Old entries reference `houba`; a header notice
   explains the rename.

## Testing

- **Full suite green** after Phase 2 (package rename) — the bulk of the test.
- **Transition tests** (Phase 3): seed `FakeRegistryPort` with old-type referrers
  (`vnd.houba.*`), assert `gc` / `purge` / `audit` recognize them.
- **Coverage gates hold**: ≥80% global, ≥90% on `knock.domain`.
- **CI green** end-to-end after Phase 4.

## Docs to sync (same change as ship)

- **ADR mirror**: `docs/architecture/decisions/0044-rename-houba-to-knock.md` (or next number).
- **C4 model**: rename system, containers, components in `workspace.dsl`; regenerate exports.
- **Examples**: all `MirrorPolicy` + README examples updated.
- **Roadmap**: add rename notice.
- **`MIGRATION.md`**: new file at repo root documenting the upgrade path.
