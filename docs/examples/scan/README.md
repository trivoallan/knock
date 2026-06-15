# Attaching a scan result (`houba attach`)

houba does not run scanners. A scan is produced **upstream** (your CI, a registry-native
scanner, or a scan service); houba ingests its report and stamps it as a portable OCI
**referrer** on the image's digest. This makes "which images carry a critical CVE?" one
referrers query at incident time.

## 1. Produce a report upstream (example: Trivy emitting SARIF)

```bash
trivy image --format sarif --output scan.sarif.json harbor.corp/lib/redis:7.2.0
```

## 2. Attach it

```bash
houba attach harbor.corp/lib/redis:7.2.0 --report scan.sarif.json
# attached sarif scan (trivy 0.50.1) → harbor.corp/lib/redis@sha256:ref…
#   subject=sha256:abc…  vuln.critical=1 vuln.high=0 vuln.medium=1 vuln.low=0 vuln.unknown=0
```

The referrer manifest carries the summary annotations (`io.houba.scan.*`) and the raw
SARIF as its blob. Re-running `attach` after a fresh scan adds a new referrer (history).

`sample.sarif.json` in this directory is a runnable example report (1 critical, 1 medium).

## 3. Sign it (verifiable scan provenance)

With a signer configured, `houba attach` also emits a **signed** in-toto attestation
(`https://houba.dev/predicate/scan/v1`) over the image digest — additive to the raw report
referrer above. This is what lets an admission controller *require* a signed scan.

```bash
export HOUBA_ATTEST_SIGNER=keyless          # or kms | key
export HOUBA_ATTEST_BUILDER_ID=houba://ci   # identifies this houba attester
houba attach harbor.corp/lib/redis:7.2.0 --report scan.sarif.json
# attached sarif scan (trivy 0.50.1) → harbor.corp/lib/redis@sha256:ref…
#   subject=sha256:abc…  vuln.critical=1 …
#   signed: https://houba.dev/predicate/scan/v1 → sha256:att…
```

Off by default: with no `HOUBA_ATTEST_SIGNER`, only the unsigned referrer is attached.

## 4. Gate CI on severity (`--fail-on`)

`attach` is observational by default (exits 0). Pass `--fail-on <severity>` to turn it into a
CI gate: if the ingested scan has any finding **at or above** the threshold, attach exits 1.

Severity order (highest to lowest): `critical > high > medium > low > unknown`.

```bash
# Fail CI when any high or critical finding is present
houba attach registry.example.com/lib/redis:7.2.0 --report scan.sarif.json --fail-on high
# attached sarif scan (trivy 0.50.1) → registry.example.com/lib/redis@sha256:ref…
#   subject=sha256:abc…  vuln.critical=1 vuln.high=0 vuln.medium=1 vuln.low=0 vuln.unknown=0
# gating: scan has a finding at or above high (--fail-on)
# exit 1
```

The raw referrer is always attached first; the gate only controls the exit code. With no
findings at or above the threshold the command exits 0 (gate passes). Use `--fail-on low` or
`--fail-on unknown` to catch every finding including unknowns.
