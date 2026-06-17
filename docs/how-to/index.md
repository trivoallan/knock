# How-to guides

Task-oriented guides — each solves one concrete problem against a running houba.

- **[Attach a scan result](attach-scan.md)** — ingest an upstream SARIF report as a signed OCI
  referrer (`houba attach`), with `--fail-on` as a severity CI gate.
- **[GC superseded scan referrers](gc-scan-referrers.md)** — reap stale scan referrers, keeping the
  newest per `(tool, format)` (`houba gc`).
- **[Purge unused tags](purge-unused-tags.md)** — the reference reaper: how marked tags get
  usage-gated and hard-deleted (`houba purge`), and how to wire your own usage oracle.
- **[Audit coverage](audit-coverage.md)** — find images that lack the stamp (`houba audit`),
  and gate CI on coverage / signing.
- **[Inspect an image's SBOM](inspect-sbom.md)** — find and fetch the SBOM referrer attached to a
  placed image, and enable CycloneDX alongside SPDX.
- **[Run the reference deployment](reference-deployment.md)** — houba as a Kubernetes CronJob
  (the kind demo *and* the production blueprint): git-synced policies, rootless buildkitd, a
  blast-radius consumer, optional KEDA autoscaling.

More task walkthroughs — mirror by semver, harden a rebuild, cap tags with retention — live
alongside the runnable [example policies](../examples/README.md) (the `.yml` policies stay in
`examples/`, since the deployment and CI run them).
