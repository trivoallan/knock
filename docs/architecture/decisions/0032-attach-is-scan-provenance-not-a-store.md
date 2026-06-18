# 32. `attach` is scan provenance, not a vuln store — the boundary with Dependency-Track

Date: 2026-06-16

## Status

Accepted.

Builds on [15. Sign the houba attach scan referrer](0015-scan-attestation.md),
[21. `attach --fail-on` CI gate](0021-attach-fail-on-gate.md),
[28. Scan-referrer garbage collection](0028-scan-referrer-gc.md).

## Context

The target org already runs **Dependency-Track** (continuous SBOM/vuln analysis: central,
queryable, re-correlated against today's feeds). That raises a redundancy question against
`houba attach`, which writes scan results as signed OCI referrers: is the referrer a second,
weaker vuln *store* competing with DT's database?

It is — *if framed as a store*. DT wins that role on every axis (central, continuous, rich,
queryable). But `attach` conflates two jobs with opposite fates in a DT shop:

- **Store** — "be the queryable vuln record." Pure redundancy with DT. Ceded.
- **Provenance** — "a signed, digest-bound, offline-verifiable attestation that *this digest was
  scanned by tool T, here is the signed result*." Not a store job at all — supply-chain provenance,
  the family of the SLSA attestation and the stamp. DT does not do this.

The org has an **admission controller** that verifies signed attestations at deploy. That makes the
provenance job load-bearing and genuinely non-redundant: admission needs a self-contained,
key-verifiable, digest-bound proof that an image came through the front door — something DT (a
query-time DB) cannot be without coupling every deploy to its API and uptime, and which DT cannot
answer anyway ("did this come through the front door?" is not a question DT can answer).

## Decision

The `attach` referrer is positioned and maintained as **signed scan provenance**, not a vuln store.
The layers are adjacent, not competing:

- **Dependency-Track = currency.** What is vulnerable *now* (query-time, central, continuous).
- **`attach` referrer = provenance.** Verified at admission (proof-time, on-artifact, offline).

The real enforcement gate is the **admission controller** verifying the signed attestation
(fail-closed) — this is what makes the single-front-door mandate hard rather than goodwill, and it
turns the `signed` audit tier (ADR 0026) into a runtime gate. `attach --fail-on` (ADR 0021) is
demoted to a coarse CI tripwire; it is no longer the reason `attach` exists.

## Guardrail (the redundancy trap, kept shut)

The admission controller verifies the **signature and digest binding** — *"was scanned, signed by
houba"* — never the **content** (currency, severity). A valid signature over a stale scan still
passes. The temptation will be to add freshness/severity correlation into the referrer; that
re-imports DT's job onto the artifact and reopens the overlap. **The referrer stays provenance.**
Staleness, if closed at admission, is closed only by a provenance-shaped **max-age** policy
("scanned recently"), never by vulnerability correlation. Currency is delegated to DT.

## Consequences

- No code change — this is a scope/positioning decision. The `attach` mechanism (ADR 0015) is
  unchanged; what changes is what we will and will not build onto it.
- **`gc` must be digest-safe** (follow-up to ADR 0028): keep-N reaping must never orphan the
  attestation a live, deployed digest depends on for admission, or it bricks deploys. Verify the
  keep-N policy cannot strand a referrer for an admitted digest.
- **No C4 change, deliberately.** Dependency-Track is the org's concrete instance of the roadmap's
  abstract "observability stack" consumer. Naming it in `workspace.dsl` would betray the
  *portable, tool-agnostic stamp* thesis — DT stays the worked-example consumer, not a modeled
  external system.

## Related

[ADR 0039](0039-scanstep-runs-the-scanner-gates-at-admission.md) extends this boundary: the reconcile
**scanstep** *invokes* an evaluator and gates placement on severity **at scan time** (the
reconcile-path analog of `attach --fail-on`, ADR 0021) — point-in-time, then recorded as provenance.
It does **not** make the referrer a vuln store, and does **not** have the admission controller
correlate severity (the guardrail above stands — the deploy-time gate remains a provenance-shaped
max-age check); *currency* stays Dependency-Track's. The C4 `vulnScanner` external system (one box,
two relations — ingested via attach, invoked via the scanstep) supersedes the old `upstreamScanner`
and the "houba never calls the scanner" wording.
