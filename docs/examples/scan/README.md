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

## 5. Roster-driven authentication

`houba attach` authenticates against the `HOUBA_REGISTRIES` roster — the same roster that
`reconcile` and `audit` use — so credentials are declared once and applied consistently.

### 5a. Host-match (default)

Set the roster and run `attach` as usual. houba parses the host from the image ref
(`harbor.corp` in the example below), finds the matching roster entry, and logs in before
touching the registry. No extra flag needed.

```bash
export HOUBA_REGISTRIES='{
  "prod": {
    "host": "harbor.corp",
    "username": "robot$houba",
    "password": "s3cr3t"
  }
}'

houba attach harbor.corp/lib/redis:7.2.0 --report scan.sarif.json
# houba matches harbor.corp → roster entry "prod", logs in, then attaches.
```

### 5b. `--registry` override

Use `--registry <name>` to force a specific roster entry regardless of the ref's host — useful
when the image is behind a pull-through proxy or the ref's host differs from the roster name:

```bash
houba attach harbor.corp/lib/redis:7.2.0 --report scan.sarif.json --registry prod
```

`--registry` with a name that is not in the roster exits 3 (`ConfigError`), consistent with the
rest of the CLI.

### 5c. Silent fallback

When no `--registry` is given and the ref's host is not in any roster entry (for example a
public image or an empty roster), `attach` configures nothing and falls back to ambient regctl
config — exactly today's behaviour. No flag and no roster entry required for public registries.

## Posture reports (rule evaluations, not vulnerabilities)

A SARIF report is not always a vulnerability scan. Policy / posture tools (for example the sibling
tool **regis**, which emits SARIF) report **rule evaluations** — each result carries an explicit
SARIF `kind` (`pass` / `fail` / …) rather than a CVSS `security-severity` score.

`houba attach` recognizes this: a result with an explicit `kind` is summarized as a rule outcome,
not a vulnerability, so a failed hygiene rule never inflates the `vuln.*` counts:

```bash
uv run houba attach --format sarif posture.sarif.json harbor.corp/lib/redis:7.2.0
# attached sarif scan (regis 1.x) → harbor.corp/lib/redis@sha256:ref…
```

The stamp then carries `io.houba.scan.rule.passed` / `io.houba.scan.rule.failed` alongside the
`io.houba.scan.vuln.*` buckets (a CVSS-scored result is always counted as a vulnerability, even if
it also carries a `kind`). The `--fail-on <severity>` gate acts on `vuln.*` only — rule failures
are reported in the stamp, not gated.
