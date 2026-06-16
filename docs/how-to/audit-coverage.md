# Audit coverage

Once images are flowing through houba, **`houba audit`** answers the coverage-gate question:
*which images in the registry do NOT carry houba's provenance stamp?* It walks the configured
registries (or a single `--registry NAME`), reads each image's annotations, and reports each as
covered or uncovered — the blind-spot report that makes the front door verifiable.

```bash
# after a reconcile, against the local registry:2 from Getting started
uv run houba audit
# UNCOVERED localhost:5001/demo/other-image:latest
# audit  scanned=13 covered=12 uncovered=1 errored=0
```

It is **read-only** (never deletes or stamps) and **report-only by default** (exit 0). For a CI
gate, pass `--fail-on-uncovered` to exit non-zero when any image lacks the stamp:

```bash
uv run houba audit --fail-on-uncovered    # exit 1 if uncovered > 0
```

An image counts as covered when it carries the houba lineage annotation (`io.houba.policy`, or
the OCI `org.opencontainers.image.base.digest` when `HOUBA_LABEL_PREFIX` is empty). `HOUBA_LOG_FORMAT=json`
emits the full structured `CoverageReport`.

## The trustworthiness tier

For the trustworthiness tier, add `--signed`: for each *stamped* image it also probes for a
signed attestation referrer (a present cosign bundle ⇒ signed; no pull-and-verify), distinguishing
*signed* from *merely stamped*:

```bash
uv run houba audit --signed
# UNSIGNED  localhost:5001/demo/legacy-image:latest
# audit  scanned=13 covered=12 uncovered=1 signed=11 unsigned=1 errored=0
```

As a CI gate, `--fail-on-unsigned` exits non-zero when any stamped image is unsigned (it implies
`--signed`):

```bash
uv run houba audit --fail-on-unsigned    # exit 1 if unsigned > 0
```
