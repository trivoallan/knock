# How-to guides

Task-oriented guides — each solves one concrete problem against a running houba.

- **[Purge unused tags](purge-unused-tags.md)** — the reference reaper: how marked tags get
  usage-gated and hard-deleted (`houba purge`), and how to wire your own usage oracle.
- **[Audit coverage](audit-coverage.md)** — find images that lack the stamp (`houba audit`),
  and gate CI on coverage / signing.
- **[Run the reference deployment](reference-deployment.md)** — houba as a Kubernetes CronJob
  (the kind demo *and* the production blueprint): git-synced policies, rootless buildkitd, a
  blast-radius consumer, optional KEDA autoscaling.

More task walkthroughs — mirror by semver, harden a rebuild, cap tags with retention, ingest a
scan with `houba attach` — live alongside the runnable [example policies](../examples/README.md)
(the `.yml` policies stay in `examples/`, since the deployment and CI run them).
