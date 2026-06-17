# Inspect an image's SBOM

Every image `houba reconcile` places carries a package-level SBOM attached as an OCI referrer (for the
what and why, see [Package-level SBOM](../explanation/sbom.md)). This guide finds and fetches it, and
enables CycloneDX alongside SPDX.

## Find the SBOM referrer

The SBOM is attached via the OCI referrers API, so any distribution-spec-compliant client discovers
it. Its `artifactType` is the SBOM media type — `application/spdx+json` (or
`application/vnd.cyclonedx+json`):

```bash
regctl image referrers registry.example.com/demo/busybox@sha256:<digest>
```

## Fetch the SBOM document

```bash
regctl manifest get registry.example.com/demo/busybox@sha256:<sbom-referrer-digest> \
  --format body | jq '.packages | length'
```

The referrer's annotations record the producing tool and version (`io.houba.sbom.tool` /
`io.houba.sbom.tool.version`), the format, and the subject digest.

## Emit CycloneDX as well as (or instead of) SPDX

SBOM generation is always-on; `HOUBA_SBOM_FORMATS` chooses the format(s) — a global, non-empty
operator setting. One `syft` scan produces one referrer per format:

```bash
HOUBA_SBOM_FORMATS='["spdx-json","cyclonedx-json"]' uv run houba reconcile docs/examples/reference
```

See the [configuration reference](../reference/config.md) for the variable.
