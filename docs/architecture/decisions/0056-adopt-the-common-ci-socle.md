# 56. Adopt the common CI socle; read the docs on GitHub

Date: 2026-10-16

## Status

Accepted. Supersedes in part [18. Publish a signed, attested image to GHCR on release](0018-publish-image-ghcr.md)
(the workflow and token that publish the image) and
[37. Docs polish — published architecture narrative + deck](0037-docs-polish-presentation.md)
(the published docs site the narrative was written for).

## Context

`regis`, `knock` and `uske` are to be published together under one organization, with the same
licence, the same community files, the same CI and the same versioned repository settings. Each
repository had grown its own CI: in knock, a hand-written `ci.yml` (with an 80 % global gate and a
second 90 % pass on `knock.domain`), `release-please.yml` with a personal access token
(`RELEASE_PLEASE_TOKEN`), a Docusaurus site under `website/` deployed to GitHub Pages by `docs.yml`,
Renovate (as a hosted app) for version updates beside Dependabot security updates for the site's
npm packages, and settings kept in `.github/settings.yml` for the Settings GitHub App. Three
repositories maintained three ways drift, and a site build is a second toolchain (Node) for pages
that GitHub already renders.

## Decision

- **knock adopts the CI socle written in `regis`, copied byte-identical**: `ci`, `pr-title`,
  `release`, `renovate`, `settings` and `socle-drift` workflows, `.github/renovate.json5`,
  `.github/apply-settings.sh` and `.github/pip-audit-gate.py`. `socle-drift` compares them weekly
  with the two other repositories. Workflows knock alone needs are named `extra-*.yml`
  (`extra-demo-mongobleed.yml`, `extra-manifests.yml`).
- **The CI only calls `make` targets** (`ci-tools`, `lint`, `test`, `security`, `image`, `smoke`):
  what is knock-specific lives in the `Makefile`. The required checks are `lint`, `test`,
  `security`, `image` and `pr-title`. `security` is a pip-audit gate blocking from HIGH.
- **One coverage gate: 90 % global branch coverage**, replacing the 80 % global and 90 % domain
  passes.
- **Releases** stay on release-please, but the token comes from a GitHub App (`oci-ci-ttc`) rather
  than a personal token. `release.yml` publishes the signed multi-arch image (cosign keyless, buildx
  SBOM and provenance) on every push to `main` as `main`, and on a release as `X.Y.Z`, `X.Y` and
  `latest`. The images to publish are listed in `.github/images.json`.
- **Repository settings** are versioned in `.github/settings.json` (rulesets, merge policy,
  security features) and applied by `.github/apply-settings.sh`, which replaces the Settings app.
  **Renovate is self-hosted** in `renovate.yml`, with OSV vulnerability alerts; the Dependabot
  configuration goes with the site, and Dependabot security updates are turned off.
- **The docs are plain Markdown read on GitHub.** The Docusaurus site and its Pages deployment are
  removed: each Diátaxis section of `docs/` has a `README.md` index, admonitions become GitHub
  alerts, front matter and Docusaurus-only link forms are gone, and `lychee` checks internal links
  in CI. `make reference` writes GitHub-ready pages.

## Consequences

- One CI to maintain for three repositories; a change to the socle is made in `regis` and copied.
- `make image` now builds `knock:ci` for CI; the target that builds `knock:dev` and loads it into
  kind is `make kind-image`.
- Every push to `main` publishes a signed `main` image, which ADR 18 left out of scope.
- The `RELEASE_PLEASE_TOKEN` secret, the Pages site and the Settings app become unused and are
  removed after the switch.
- The architecture narrative of ADR 37 stays where it is (`docs/explanation/architecture.md`); it is
  now read on GitHub, where Mermaid diagrams render natively.
- The runnable example files are linked from the catalog pages under `docs/reference/examples/`
  rather than inlined, since GitHub has no code-import.
