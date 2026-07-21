# 39. SARIF `kind` discriminates a policy verdict from a vulnerability finding

Date: 2026-06-19

## Status

Accepted

Supersedes [27. Finding-type-aware SARIF mapper](0027-sarif-finding-type.md).

## Context

ADR 0027 made the SARIF mapper route an explicit `kind` to a binary `rule.passed`/`rule.failed`,
but only when no CVSS `security-severity` was present — the score always won. The sibling tool
regis (PR #789) emits policy **verdicts** as SARIF carrying *both* a `security-severity` (mapped
from the verdict level) and the verdict's own severity. Under 0027 those verdicts inflate
`vuln.*`, and the binary `rule.*` discards the verdict severity (a license-violation critical and a
label-hygiene low look identical). Governance is the value regis adds beyond CVEs; the stamp must
carry it truthfully and at severity granularity.

## Decision

An explicit SARIF `result.kind` marks an **evaluation outcome** (a governance verdict) and **wins
over** the CVSS score. Verdicts are summarized in a severity-bucketed `policy.*` space:
`kind:"pass"` → `policy.passed`; otherwise `policy.<severity>`, bucketed by the result's
`security-severity` (else its `level`). A result **without** `kind` is a finding → `vuln.*`
(unchanged). knock keys on the standard `kind` signal, **never on `tool.driver.name`** — any
analyzer emitting `kind` gets governance bucketing, so the split stays analyzer-agnostic. This
replaces the binary `rule.passed`/`rule.failed` (annotation keys `io.knock.scan.rule.*` →
`io.knock.scan.policy.*`); acceptable as a breaking change in 0.x, where no producer emitted
`rule.*` yet.

The `--fail-on <severity>` gate is unchanged (acts on `vuln.*` only); policy verdicts are reported
in the stamp, not gated. No native regis mapper, no new format, no new port/adapter/actor/external
system. **C4 model: unchanged.** The scan summary remains an open `dict[str, str]`, so no schema
regeneration.

## Consequences

- Governance verdicts are queryable as `scan.policy.<severity>` / `scan.policy.passed`, preserving
  the verdict's severity — distinct from vulnerabilities, ready for a governance view.
- A `kind`-bearing result with a CVSS score is now a verdict, not a vulnerability (the 0027
  ordering is reversed). This is intentional: a tool that sets `kind` is declaring a verdict.
- regis emitting `kind:"fail"`/`"pass"` is a parallel sibling-repo change (PR #789 follow-up); the
  knock change is testable without it via synthetic SARIF fixtures.

Full design spec: [2026-06-19-sarif-kind-policy-classification-design.md](../../superpowers/specs/2026-06-19-sarif-kind-policy-classification-design.md)
