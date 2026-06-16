# How-to guides

Task-oriented guides — each solves one concrete problem against a running houba.

- **[Run the reference deployment](reference-deployment.md)** — houba as a Kubernetes CronJob
  (the kind demo *and* the production blueprint): git-synced policies, rootless buildkitd, a
  blast-radius consumer, optional KEDA autoscaling.

More guides — mirror by semver, harden a rebuild, cap tags with retention, delegated deletion,
reap with `houba purge`, ingest a scan with `houba attach`, run the coverage audit — currently
live as the runnable [example policies](../examples/README.md) catalog and will move here as
standalone guides (the `.yml` policies stay in `examples/`, since the deployment and CI run them).
