# Finding-type-aware SARIF mapper

Date: 2026-06-16
Status: Design (approved)
Roadmap: *Now* — "Scan ecosystem breadth", reframed. Builds on `knock attach` (ADR 0006/0015) and
the pluggable scan-format registry.

## Problem

`knock attach` ingests scan reports as signed OCI referrers and summarizes them into a queryable
`{prefix}.scan.*` stamp. Today the only mapper is `SarifMapper`, and it buckets **every** SARIF
result into `vuln.<severity>` (by CVSS `security-severity`, else by `level`).

The sibling tool **regis** is a *posture* evaluator (pass/fail rule evaluations, EOL, hygiene
scopes, tiers) and will emit SARIF. Run through today's mapper, a failed hygiene rule or an
end-of-life finding is counted as a *vulnerability* — inflating `vuln.*`, corrupting the
blast-radius query, and tripping `--fail-on <severity>` for non-vuln reasons. Since *the label is
the product*, a misleading stamp is worse than no stamp.

The fix is **semantic, not transport**: teach the SARIF mapper to tell a vulnerability finding
apart from a rule/policy evaluation, using only standard SARIF — no regis-specific knowledge, no
new format (CLAUDE.md: org-specific behavior must be configuration of generic primitives, never
hardcoded; here, regis-specific behavior is likewise forbidden — knock handles SARIF per spec).

## Decision

Make `SarifMapper.summarize` classify each result, in priority order:

1. **CVSS score present** (`security-severity` on the result's `properties`, else on the matched
   rule) → `vuln.<critical|high|medium|low>` by score. *Unchanged. The score always wins.*
2. **Else, an explicit `kind` key on the result** → a rule/policy evaluation:
   - `kind == "pass"` → `rule.passed`
   - any other value (`fail`, `open`, `review`, `notApplicable`, `informational`, …) →
     `rule.failed`
3. **Else** (no CVSS, no `kind`) → the existing `level` fallback → `vuln.<severity>`. *Unchanged.*

Routing to `rule.*` triggers **only when the `kind` key is explicitly present**. Existing
SARIF producers (Trivy, linters) that omit `kind` keep today's exact behavior — strictly additive,
zero regression.

### Fact vocabulary

`SarifMapper.fact_keys` becomes `vuln.<bucket>… + ("rule.passed", "rule.failed")`. The `facts`
dict always carries every key (zero-filled), like the vuln buckets. `vocabulary.py` derives the
published key list from `fact_keys`, so `scan.rule.passed` / `scan.rule.failed` appear
automatically; no hand-editing.

### Gate

`gate_breached` / `--fail-on <severity>` is **unchanged** — it operates on `vuln.*` only. A failed
rule is *reported* in the stamp, not *gated*, in this version. A future `--fail-on-rule` is
deliberately deferred (YAGNI).

### Annotations

`build_scan_annotations` already prefixes facts generically, so `{prefix}.scan.rule.passed` /
`.failed` are emitted with no code change.

## Ceiling (accepted)

A tool that sets `kind:"fail"` on a genuine vulnerability *without* any CVSS score would be counted
as `rule.failed`. Pathological (real vuln scanners carry CVSS). Marked with a `ponytail:` comment;
upgrade path is to read a SARIF taxonomy/tag if such a producer ever appears.

A result carrying *both* a CVSS score and `kind:"pass"` is counted as a vuln (rule 1 wins) — a
scored finding is a finding regardless of kind.

## Out of scope

- New format mappers (CycloneDX, Trivy-native) — Trivy already emits SARIF; CycloneDX is a
  separate transport, added only on real demand. A native regis mapper is explicitly rejected in
  favor of the SARIF projection.
- Gating on rule failures (`--fail-on-rule`).
- Surfacing regis tiers/badges/by-tag scoring — these have no standard SARIF home; only what SARIF
  carries (rule results) is summarized.

## Testing

- `kind:"pass"` → `rule.passed`; `kind:"fail"`/`"open"` → `rule.failed`.
- CVSS score **and** `kind:"pass"` → still `vuln.*` (score precedence).
- Existing fallbacks stay green: `level`-only (no `kind`) → `vuln.*`; `[{}]` → `vuln.unknown`.
- `no_results` summary includes `rule.passed`/`rule.failed` == "0".
- `scan_annotation_vocabulary()` publishes `scan.rule.passed` / `scan.rule.failed`.

## Docs / C4

No new port, adapter, mapper, actor, or external system — `SarifMapper` gains finding-type
awareness in place. **C4 model: unchanged** (note this in the ADR). Add a thin ADR and extend
`docs/examples/scan/README.md` with a posture-report (regis-via-SARIF) walkthrough showing the
`scan.rule.*` facts.
