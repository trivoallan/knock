# Runbook — Capture production fixtures

## Purpose

Build a set of Harbor fixtures (real upstream snapshots) for development and snapshot testing. These fixtures let the test suite assert behaviour on real-world data without ever touching production at test time.

## Prerequisites

- A read-only robot account on your production Harbor instance.
- Environment variables populated (see [README](../../README.md#configuration)).
- `houba` available locally, either from source (`uv run houba`) or as a Docker image (`docker run --rm -e HOUBA_HARBOR_URL=... houba:v0-rc`).

## Picking products to capture

Aim for **10 to 20 captures** covering the edge cases your tag-selection logic must handle:

| Case | Suggestion |
|---|---|
| Simple product (few tags) | `library/busybox` |
| Dense semver | `rancher/k3s` |
| Product with end-of-life data | `library/redis` |
| Product with regex exclusions | (project-specific) |
| Product with shifting digest under a moving tag | `library/nginx:stable` |
| Multi-tag (alias) | (project-specific) |
| Already archived product | (project-specific) |

## Procedure

For each product:

```bash
houba dev capture \
  --project <project> \
  --repository <repository> \
  --output tests/fixtures/captured/
```

This writes JSON files under `tests/fixtures/captured/` capturing the repository state, all tags, all artifacts, and (where applicable) the linked `properties.yml`.

## Anonymisation

Before committing the fixtures, verify no sensitive data has leaked:

- Robot account names (`robot$...`)
- Internal URLs
- Auth tokens

A quick `grep -rE 'robot\$|<your-internal-domain>' tests/fixtures/captured/` is usually enough. Strip or substitute anything that surfaces.

## Commit

```bash
git add tests/fixtures/captured/
git commit -m "test(fixtures): initial production capture (N fixtures)"
```

Captured fixtures **block the merge to main** of any change that breaks them: snapshot tests compare current behaviour against the recorded outputs and flag regressions immediately.
