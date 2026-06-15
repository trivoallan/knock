# Design — Publish signed, attested multi-arch image to GHCR on release

- **Date:** 2026-06-15
- **Status:** approved (design), pending implementation plan
- **Scope:** CI / release infrastructure. Add a `publish` job to `release-please.yml` that, on each
  release, builds and pushes a multi-arch (`amd64` + `arm64`) image to `ghcr.io/<owner>/houba` with
  an SBOM + SLSA provenance (buildx attestations) and a keyless `cosign` signature. Update the
  README Install section; add a thin ADR. **No** application code, port, adapter, domain, or config
  change.

## Problem

CI already builds the runtime image (`ci.yml` → `docker-build` job) but with `push: false` — it only
smoke-tests the image locally and **never publishes it**. Meanwhile the README Install section
already promises:

```
docker pull ghcr.io/<your-org>/houba:0.4
```

— a doc/reality gap, with an unresolved `<your-org>` placeholder. There is no published image to pull.

houba's product thesis is *"the label is the product"*, and it ships **signed SLSA / in-toto
attestations** for the images it stamps. Its own distributed image should therefore be exemplary:
**signed and attested**, so a consumer can verify provenance *before* running the very tool that
verifies everyone else's provenance. `cosign` is already bundled in the runtime image and available
on the GitHub-hosted runner, so the supply-chain tooling is already in hand.

## Decision

Publish on **release only**, as a **signed + attested multi-arch** image, via the **cosign-native**
mechanism. The four locked choices:

1. **Trigger — release only, wired as a job inside `release-please.yml`.**
   GitHub does not trigger workflows from events emitted by `GITHUB_TOKEN` (the existing
   `release-please.yml` already notes this for PRs). A separate `on: release: published` workflow
   would therefore fire unreliably (only when the `RELEASE_PLEASE_TOKEN` PAT authors the release).
   Instead, add a second job `publish` to `release-please.yml`, gated by
   `if: needs.release-please.outputs.release_created`. It runs in the **same** workflow run (triggered
   by the merge push to `main`), so it always fires after a release is cut and reads the
   version/tag straight from release-please's job outputs. This sidesteps the token-triggering gotcha
   entirely. *(Alternative considered: standalone `publish-image.yml` on `release: published` —
   cleaner separation but depends on the PAT to fire. Rejected for robustness.)*

2. **Mechanism — cosign-native (approach A).**
   `docker/build-push-action` builds and pushes the multi-arch index **by digest** with
   `sbom: true` and `provenance: mode=max`, attaching an SPDX **SBOM** and a SLSA **provenance**
   statement as OCI referrers. Then `cosign sign` signs the pushed digest **keyless** (OIDC via the
   workflow `id-token`, Fulcio + Rekor — **no signing secrets**). Coherent with the cosign tooling
   already in the repo and the bundled `cosign` binary; fully verifiable with `cosign verify` /
   `cosign verify-attestation`. *(Alternatives considered: B — GitHub `attest-build-provenance` /
   `attest-sbom` for Sigstore-signed attestations, stronger but two ecosystems and more steps; C —
   houba dogfooding its own image, rejected as circular and outside the attestor's third-party-image
   use case. Both recorded in Out of scope.)*

3. **Architectures — `linux/amd64` + `linux/arm64`.**
   Cheap here: houba is pure-Python, so the built wheel is architecture-independent; only the
   `python:3.12-slim` base and the three bundled binaries (`buildctl`, `regctl`, `cosign`) differ per
   arch, and all are multi-arch upstream. `buildx` + QEMU emulation covers the `apt`/`pip` steps.

4. **Naming & tags.**
   Image reference `ghcr.io/${{ github.repository_owner }}/houba` — **generic in the YAML** (no org
   hardcoded; a fork publishes to its own namespace). The canonical public image is
   `ghcr.io/trivoallan/houba` (the repo owner, already present as `homepage` in
   `.github/settings.yml`). Tags per release: `X.Y.Z` (immutable) + `X.Y` (moving, the README's
   `:0.4`) + `latest`, derived from release-please outputs. OCI labels
   (`org.opencontainers.image.{source,revision,version,created,licenses,description}`) are injected at
   build time so GHCR auto-links the package to the repo and renders the README on the package page —
   consistent with *"the label is the product"*: houba's own image carries its own labels.

## Implementation

A new `publish` job in `.github/workflows/release-please.yml`, gated on `release_created`, with
job-scoped permissions. Shape (final wording settled in the plan):

```yaml
permissions:
  contents: read          # default for the workflow; release-please job overrides as today

jobs:
  release-please:
    # ... unchanged; must expose outputs: release_created, version, major, minor, tag_name
    permissions:
      contents: write
      pull-requests: write

  publish:
    needs: [release-please]
    if: ${{ needs.release-please.outputs.release_created }}
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write       # push to GHCR
      id-token: write       # cosign keyless OIDC
    steps:
      - uses: actions/checkout@v6
      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository_owner }}/houba
          tags: |
            type=raw,value=${{ needs.release-please.outputs.version }}
            type=raw,value=${{ needs.release-please.outputs.major }}.${{ needs.release-please.outputs.minor }}
            type=raw,value=latest
      - id: build
        uses: docker/build-push-action@v7
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          sbom: true
          provenance: mode=max
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - uses: sigstore/cosign-installer@v3
      - name: Sign image (keyless)
        env:
          IMAGE: ghcr.io/${{ github.repository_owner }}/houba
          DIGEST: ${{ steps.build.outputs.digest }}
        run: cosign sign --yes "${IMAGE}@${DIGEST}"
      - name: Smoke test pushed image
        run: docker run --rm "ghcr.io/${{ github.repository_owner }}/houba@${{ steps.build.outputs.digest }}" version
```

Notes:
- `release-please` job outputs (`release_created`, `version`, `major`, `minor`, `tag_name`) must be
  surfaced via the action's `outputs` — wire them through the job's `outputs:` map.
- `cosign sign` on the **index digest** covers the multi-arch manifest; the smoke `docker run @digest`
  pulls the runner-native (amd64) variant. A red smoke fails the release job (the release commit was
  already CI-green on `main`, so this is a belt-and-braces guard).
- README **Install** section: resolve the placeholder to `ghcr.io/trivoallan/houba` and add a
  verification block:
  ```bash
  docker pull ghcr.io/trivoallan/houba:0.4
  cosign verify ghcr.io/trivoallan/houba:0.4 \
    --certificate-identity-regexp 'https://github.com/trivoallan/houba/.*' \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com
  cosign verify-attestation --type spdxjson ghcr.io/trivoallan/houba:0.4 \
    --certificate-identity-regexp 'https://github.com/trivoallan/houba/.*' \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com
  ```
- **Bootstrap (one-time, manual):** after the first release, set the GHCR package visibility to
  **Public** (UI or `gh`). The repo↔package link is established automatically by the
  `org.opencontainers.image.source` label.

## Files

- **Modify** `.github/workflows/release-please.yml` — add the `publish` job + job outputs.
- **Modify** `README.md` — Install section: resolve `<your-org>` → `ghcr.io/trivoallan/houba`; add the
  `cosign verify` / `verify-attestation` block.
- **Add** `docs/architecture/decisions/0018-publish-image-ghcr.md` — thin ADR pointing to this spec.
- **No change** to `ci.yml` (the PR/main `docker-build` smoke job stays `push: false`), to
  `.github/settings.yml` (the publish job is not a PR status check), or to `pyproject.toml`.

## Testing

No unit tests (the change is workflow YAML + docs). Verification is:

1. **Static:** `actionlint` on the edited workflow (if available); confirm `release-please` outputs
   are correctly threaded.
2. **Post-release checklist** (run after the first release cut on this design):
   - `docker pull --platform linux/amd64` **and** `--platform linux/arm64` both succeed.
   - `docker buildx imagetools inspect ghcr.io/trivoallan/houba:<v>` shows a multi-arch index **and**
     the SBOM + provenance referrers.
   - `cosign verify …` (identity regexp + OIDC issuer) succeeds.
   - `cosign verify-attestation --type spdxjson …` succeeds.
   - `X.Y.Z`, `X.Y`, and `latest` all resolve to the **same** digest.
   - The GHCR package page links to the repo and renders the README.

Existing CI gates are unaffected (no Python change): `uv run pytest` (≥ 80 % global, ≥ 90 %
`houba.domain`), `ruff`, `mypy houba` stay green.

## Out of scope

- `edge` / dev images on `main` pushes (release-only by decision).
- Approach B — GitHub `attest-build-provenance` / `attest-sbom` (Sigstore-signed attestations at
  rest). Revisit only if "signed provenance predicate" (beyond the signed image + buildx attestations)
  becomes a hard requirement.
- Approach C — houba stamping its own image (circular; outside the attestor's third-party use case).
- Refactoring `ci.yml` to build-once-and-promote. The release build is independent of the CI smoke
  build; the shared `type=gha` cache keeps the cost low. YAGNI.
- `cosign` key / KMS signing (keyless only).
- Automating GHCR package visibility (one-time manual step).

## Architecture / C4

- **ADR:** add `0018-publish-image-ghcr.md` — a supply-chain / distribution decision, sibling to
  `0005-registry-tls-and-runtime-image` and `0006-slsa-attestation`.
- **`workspace.dsl`:** no change to the structural (Container / Hexagon / Component) views —
  publishing to GHCR is release/distribution infrastructure, not a runtime port, adapter, actor, or
  integration of the hexagon. The implementer should confirm against the model; at most a one-line
  note in a Deployment view's description (distribution channel), which is optional and not a model
  change. No `examples/` change (this is project infra, not a `MirrorPolicy` feature).
