# 18. Publish a signed, attested image to GHCR on release

Date: 2026-06-15

## Status

Accepted

Builds on [5. Registry TLS & runtime image](0005-registry-tls-and-runtime-image.md) and
[6. SLSA / in-toto attestation](0006-slsa-attestation.md).

## Context

CI builds the runtime image but with `push: false` — it is smoke-tested and discarded, never
published. The README Install section already promises `docker pull ghcr.io/.../knock`, an
unfulfilled doc/reality gap. knock's thesis is "the label is the product", and it ships signed
SLSA / in-toto attestations for the images it stamps; its own distributed image should be exemplary
so a consumer can verify provenance before running the verifier itself.

## Decision

Publish on every release, as a multi-arch (`amd64` + `arm64`) image to `ghcr.io/<owner>/knock`, via a
`publish` job added to `release-please.yml`, gated on `release_created`. Running it in the same
workflow run as release-please sidesteps the gotcha that a tag/release created by `GITHUB_TOKEN` does
not trigger a separate workflow. `docker/build-push-action` pushes by digest with `sbom: true` +
`provenance: mode=max` (buildx SBOM + SLSA provenance referrers); `cosign sign` then signs the digest
keyless (OIDC -> Fulcio / Rekor, no signing secrets). Tags: `X.Y.Z` / `X.Y` / `latest`, plus OCI
labels that link the package to the repo.

## Consequences

- The README's `docker pull` becomes real; users can `cosign verify` the signature and inspect the
  buildx SBOM / provenance (`docker buildx imagetools inspect`) before running knock. No new
  application code, port, adapter, or config — CI/release infrastructure only.
- The publish job needs `packages: write` + `id-token: write`; the `RELEASE_PLEASE_TOKEN` PAT remains
  useful for the release PR's CI but is **not** required for publishing (same-run wiring).
- One-time bootstrap: set the GHCR package visibility to Public after the first release.
- Approaches not taken: GitHub `attest-*` Sigstore-signed attestations (heavier, two ecosystems) and
  knock dogfooding its own image (circular). `edge` / dev images are out of scope.

Full design spec: [2026-06-15-publish-image-ghcr-design.md](../../superpowers/specs/2026-06-15-publish-image-ghcr-design.md)
