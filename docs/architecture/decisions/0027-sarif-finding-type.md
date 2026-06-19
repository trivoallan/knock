# 27. Finding-type-aware SARIF mapper

Date: 2026-06-16

## Status

Superseded by [39. SARIF `kind` discriminates a policy verdict from a vulnerability finding](0039-sarif-kind-discriminates-policy-from-vuln.md)

Builds on [6. SLSA / in-toto attestation](0006-slsa-attestation.md) and the pluggable scan-format
registry.

## Context

`houba attach` summarized every SARIF result into `vuln.<severity>`. The sibling tool regis is a
posture evaluator (pass/fail rules, EOL, hygiene) that will emit SARIF; run through that mapper, a
failed rule or an end-of-life finding was miscounted as a vulnerability — corrupting the
blast-radius query and tripping `--fail-on <severity>` for non-vuln reasons. Since the label is the
product, a misleading stamp is worse than no stamp.

## Decision

Classify each SARIF result, in priority order: a CVSS `security-severity` score →
`vuln.<severity>` (unchanged, score always wins); else an explicit SARIF `kind` key → a rule
evaluation (`kind:"pass"` → `rule.passed`, anything else → `rule.failed`); else the legacy `level`
fallback → `vuln.<severity>` (unchanged). Routing to `rule.*` triggers **only** on an explicit
`kind`, so existing producers (Trivy, linters) that omit it are unaffected — strictly additive.

The fix is generic SARIF semantics, not regis-specific code; any posture tool emitting SARIF
benefits. The `--fail-on <severity>` gate is unchanged (acts on `vuln.*` only); a `--fail-on-rule`
is deferred. No native regis mapper, no new format (CycloneDX/Trivy-native deferred to real
demand). No new port, adapter, mapper, actor, or external system. **C4 model: unchanged.**

## Consequences

- Posture findings are queryable as `scan.rule.passed` / `scan.rule.failed`, distinct from
  vulnerabilities — the stamp stays truthful for non-vuln scanners.
- Accepted ceiling: a producer that sets `kind:"fail"` on a genuine vulnerability without any CVSS
  score would be counted as `rule.failed`; pathological for CVSS-emitting scanners.

Full design spec: [2026-06-16-sarif-finding-type-design.md](../../superpowers/specs/2026-06-16-sarif-finding-type-design.md)
