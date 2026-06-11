# Image transform / hardening — design (Phase 6)

> **Status:** approved design, pre-implementation. Builds on the MirrorPolicy reconcile
> (copy path, v0.2.0). The terminal step after this spec is `writing-plans`.

## 1. Context & motivation

houba is a **stamper / single front door** for external OCI images. v0.2.0 ships the
**copy path** — mirror + provenance stamp via `regctl`. This phase adds the **rebuild
path**: re-build a source image through a declarative **hardening policy** (internal CA
trust, internal package mirrors) and stamp the result. This is the essentialization the
roadmap calls for — the org-specific Groovy scripts (`add_*_sources.sh`, `get_*_keyring`,
`set_timezone.sh`, `update_keystore.sh`) become *configuration* of generic, composable,
auditable primitives, never hardcoded behavior.

## 2. Scope (v1)

**In:**
- Two transform primitives: **`injectCA`** (internal CA certs into the image trust store)
  and **`rewritePackageSources`** (apt/apk sources → internal mirror).
- **Named references**: the policy names the CA(s)/mirror; org-specific data lives in
  config (resolved by name, like the Phase 4 registry roster).
- **Single-platform rebuild** (default `linux/amd64`, configurable). The copy path stays
  multi-arch (index); rebuild produces and stamps a single-platform manifest.
- **Transform-aware change detection**: rebuild when the source moved *or* the resolved
  transform changed.

**Out (deferred):** other primitives (`set-timezone`, `set-label`, Java keystore); a `run`
escape hatch (breaks declarativeness/auditability — explicitly rejected); multi-platform
rebuild; per-import platform fan-out. Infra (separate tasks, not this spec): add `regctl`
to the runtime image alongside `buildctl`; native per-registry TLS/auth wiring for regctl.

**v1 limitation — `rewritePackageSources` covers the classic source formats only:** the
host-swap rewrites `/etc/apt/sources.list` + `/etc/apt/sources.list.d/*.list` (one-line apt)
and `/etc/apk/repositories`. It does **not** yet touch the deb822 `/etc/apt/sources.list.d/*.sources`
format that ships by default on Ubuntu 24.04+ / Debian 12 — hardening a base image that uses
deb822 will leave its package sources pointing upstream. Extending the rewrite to deb822
(`URIs:` lines) is a follow-up.

## 3. The transform vocabulary

`TransformStep` (Phase 1: single-key map `{stepName: params}` → `{name, params}`) is
unchanged structurally. This phase adds **vocabulary validation** — only the two known
step names are accepted, with validated param shapes:

```yaml
spec:
  defaults:                            # transform may also sit per-import / per-variant
    transform:
      - injectCA: { certs: [corp-root, partner-ca] }   # names → config
      - rewritePackageSources: { mirror: corp }         # name → config
```

- **`injectCA.certs`** — non-empty list of **CA names** (strings). Resolved from config.
- **`rewritePackageSources.mirror`** — a single **mirror name** (string). Resolved from config.

A pure domain function **`validate_transform_steps(steps)`** rejects any unknown step name
or malformed params with `PolicyValidationError`, run during the load-and-validate phase
(§8 of the MirrorPolicy spec), before any mutation. (The published policy JSON Schema stays
at the generic `{name, params}` level; the vocabulary check is a domain validator. Typing
the vocabulary as a discriminated union in the schema is a later refinement.)

The policy stays **portable**: only names, never an org URL or cert.

## 4. Config: the named transform-data rosters

Two new env-driven config blocks (same shape as the Phase 4 registry roster), under
`config.py` (the only place env is read):

```bash
# name → CA cert SOURCE: a file path (k8s-mountable) is primary; inline PEM is a fallback.
HOUBA_TRANSFORM_CA_CERTS='{"corp-root": {"path": "/etc/houba/certs/corp-root.pem"}, "partner-ca": {"path": "/etc/houba/certs/partner.pem"}}'

# name → per-package-manager mirror URLs
HOUBA_TRANSFORM_PACKAGE_MIRRORS='{"corp": {"apt": "https://mirror.corp/debian", "apk": "https://mirror.corp/alpine"}}'
```

- `CACertSource` — `{path: str}` **or** `{pem: str}` (inline, for local tests). Path primary.
- `PackageMirror` — `{apt?: url, apk?: url}` (per-manager; absent manager = not rewritten).
- `TransformSettings` on `Settings`: `ca_certs: dict[str, CACertSource]`,
  `package_mirrors: dict[str, PackageMirror]`, both defaulting to `{}`.
- Pure resolvers (raise `ConfigError` on an unknown name, like `resolve_registry`):
  - `resolve_ca_certs(names, roster) -> list[CACertSource]`
  - `resolve_mirror(name, roster) -> PackageMirror`

## 5. The rebuild engine

For a variant whose effective `transform` is **non-empty**, the reconcile apply step
**rebuilds** instead of copying. The existing `ImageBuilderPort`
(`BuildRequest(dockerfile_path, context_dir, image_ref, build_args)` → `build_and_push`,
backed by `buildctl`) is reused; `BuildRequest` gains an optional `platform` field.

Flow (per output tag to import/update):

1. **Resolve** the variant's transform steps against `TransformSettings` (cert sources +
   mirror config). Unknown name → `ConfigError`.
2. **Render** the Dockerfile — pure domain `render_dockerfile(source_ref, resolved_steps)`
   → `(dockerfile_text, context_filenames)`:
   ```dockerfile
   FROM docker.io/library/redis@sha256:…              # source pinned to its digest
   COPY corp-root.pem partner-ca.pem /usr/local/share/ca-certificates/   # injectCA
   RUN update-ca-certificates
   RUN <rewrite /etc/apt/sources.list[.d] | /etc/apk/repositories to the mirror>  # rewritePackageSources
   ```
   Each step contributes an ordered Dockerfile fragment plus the context files it needs
   (cert filenames). `rewritePackageSources` emits a distro-agnostic snippet that rewrites
   whichever of apt/apk is present, using the resolved per-manager URLs.
3. **Stage** a build context under `work_dir`: write the Dockerfile, copy each named cert
   file (from its config path, or write inline PEM) into the context. (I/O — application
   layer, not domain.)
4. **Build & push**: `build_and_push(BuildRequest(dockerfile, context, dest_ref,
   platform=<config default linux/amd64>))`.
5. **Stamp**: `registry.annotate(dest_ref, stamp)` — the same OCI provenance stamp as the
   copy path, **plus** the transform lineage (§6). (Stamp via `regctl image mod`, not
   buildctl LABELs — consistent with copy; annotations live on the manifest.)

`render_dockerfile` and the per-step fragment builders are **pure**. Staging + build +
stamp are the application layer.

## 6. Transform lineage & change detection

The stamp on a rebuilt image carries, in addition to the standard OCI facts:

- `io.houba.transform.steps` — e.g. `"injectCA,rewritePackageSources"` (applied, in order).
- `io.houba.transform.version` — a **content hash** of the resolved transform: the step
  names/params **and** their resolved data (CA cert *contents*, mirror URLs). Rotating a CA
  or changing a mirror URL changes this hash even if the policy text is unchanged.

`base.digest` remains the **source** digest (the rebuilt image's base *is* the source — the
idempotency key for source change detection is unchanged).

Change detection (`domain/reconcile.py`) extends:

- `MirrorArtifact` gains `transform_version: str | None` (read from the mirror's
  `io.houba.transform.version` annotation).
- The desired `transform_version` is computed from the resolved transform (pure hash over
  the read cert contents + mirror URLs — the contents are read in the application layer and
  passed in).
- `_classify` becomes transform-aware:
  - `mirror.base_digest != source.digest` → **source moved** → the 7-day stability window
    applies (skip if too recent).
  - `mirror.transform_version != desired` → **transform config changed** → rebuild **now**
    (operator-intentional; no grace window).
  - both match → **skip**.

Copy-path variants (no transform) keep `transform_version = None` on both sides → the
existing behavior, unchanged.

## 7. Reconcile integration

`use_cases/reconcile.py` apply branches **per variant**:

- `variant.transform` empty → **copy path** (existing: `copy` + `annotate`).
- `variant.transform` non-empty → **build path** (§5: resolve → render → stage → build →
  annotate-with-lineage).

The plan phase (expand + collision) is unchanged. `reconcile_import` / `_classify` carry the
`transform_version` for transformed variants. The use case is wired with the `builder`
(already in the container) and `TransformSettings` (from `Settings`).

## 8. Architecture — new/changed units

| Unit | Responsibility | Purity |
| --- | --- | --- |
| `domain/transform.py` (new) | `validate_transform_steps` (vocabulary), `render_dockerfile` + per-step fragment builders, `transform_version` (pure hash over resolved data) | pure |
| `config.py` | `CACertSource`, `PackageMirror`, `TransformSettings`, `resolve_ca_certs`, `resolve_mirror` | env + pure resolvers |
| `domain/reconcile.py` | `MirrorArtifact.transform_version`; transform-aware `_classify` | pure |
| `use_cases/reconcile.py` | copy/build branch; build path = resolve + read cert files + render + stage context + `build_and_push` + annotate | application (I/O) |
| `ports/image_builder` + `adapters/buildkit_cli` | reused; `BuildRequest.platform` added | adapter |

Error mapping (no new types): invalid transform **vocabulary/params** → `PolicyValidationError`
(exit 1, a policy fault); unknown referenced **CA/mirror name** → `ConfigError` (exit 3).

The hexagonal rule holds: domain stays pure (rendering, hashing, validation, classification);
all file/registry/build I/O is in the use case + adapters; `os.environ` only in `config.py`.

## 9. Deployment (Kubernetes) — documentation, not coupling

houba is **env-driven and orchestrator-agnostic** — it never reads the Kubernetes API. In a
k8s deployment, ConfigMaps/Secrets feed it through the standard projection mechanisms:

- **ConfigMap → env** (`envFrom`): `HOUBA_REGISTRIES`, `HOUBA_TRANSFORM_PACKAGE_MIRRORS`,
  and other non-secret `HOUBA_*` settings.
- **Secret/ConfigMap → volume**: CA cert files mounted at e.g. `/etc/houba/certs/`, with
  `HOUBA_TRANSFORM_CA_CERTS` mapping each logical name to its mount path.

This keeps houba runnable identically in local/CI/any orchestrator — k8s is one deployment
target, not a dependency. (Reading the k8s API directly would reintroduce coupling and
defeat the extraction thesis.)

## 10. Testing

- **Domain (pure)**: `validate_transform_steps` (accept the two, reject unknown/malformed);
  `render_dockerfile` (golden Dockerfile per step combination, distro-agnostic snippet);
  `transform_version` (stable for same input, changes when cert content / mirror / steps
  change); transform-aware `_classify` (source-moved vs transform-changed vs both-match).
- **Config**: roster parse from env (path + inline PEM), resolvers + `ConfigError`.
- **Adapter**: `BuildkitAdapter` already fake-bin-tested; add the `platform` arg assertion.
- **Use case** (with fakes): build branch fires `build_and_push` with the right request +
  `annotate` with the lineage; copy branch unchanged; transform change → rebuild, unchanged
  → skip (idempotent).
- Coverage gates unchanged (≥ 80 % global, ≥ 90 % domain).
