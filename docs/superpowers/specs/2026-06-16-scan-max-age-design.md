# Scan attestation max-age — a freshness contract for admission

Date: 2026-06-16
Status: Designed (pending implementation plan)

## Context

ADR 0032 (PR #135) drew the boundary between houba and Dependency-Track: the `attach`
referrer is **signed scan provenance**, not a vuln store. An admission controller verifies the
*signature and digest binding* — *"this digest was scanned, signed by houba"* — but **never the
content**. Its explicit consequence: a valid signature over a stale scan still passes. The named
remedy, and the only one inside the boundary, is a **provenance-shaped max-age** ("scanned
recently") — never vulnerability correlation, which stays Dependency-Track's job (currency).

This spec adds that max-age notion. The gap it closes: admission can prove *"was scanned & signed"*
but not *"scanned recently enough to trust."*

## Decisions

Three forks, resolved during brainstorming:

1. **Locus = producer-side.** houba *produces* a trustworthy freshness fact; the **admission
   controller enforces** the max-age policy against it. This is the ADR-0032-aligned locus ("the real
   gate is admission"). houba does **not** gain an audit-side freshness tier — an audit tier reports
   drift but cannot block a deploy, so it does not close the gap admission leaves.
2. **Clock = attach-time.** The freshness clock is the **existing** signed
   `ScanPredicate.attested_at` (ISO-8601, set to `clock.now()` at attach). No new predicate field;
   the frozen `/scan/v1` schema is **unchanged**. Semantics: *"houba (re)attached a scan at T"* — a
   provenance fact (houba's own signed claim about its own action). Rejected: a scanner report-time
   field, which is format-dependent (often absent in SARIF) and would mutate a frozen public API for
   marginal truthfulness.
3. **Example tool = Kyverno.**

## What this is — and is not

houba's deliverable is to make an **existing** contract explicit and demonstrate it. **Zero new
domain logic. Zero schema field.** The freshness fact already ships, signed; what is missing is the
stated contract (a field description — and, until now, the predicate schema was derivable via
`scan_predicate_json_schema()` but never *rendered* to `docs/reference/`, so the contract was not
actually published), the documented precondition, and a worked admission example.

## Changes

1. **Contract prose.** Add `Field(description=...)` to `ScanPredicate.attested_at` in
   `houba/domain/scan/attestation.py`: the signed attach timestamp; the freshness clock an admission
   controller gates on via max-age; the *only* trustworthy (signed) source — not the unsigned
   `{prefix}.scan.timestamp` annotation.

2. **Publish the scan-predicate schema.** Add a `scan-predicate` entry to the `SCHEMAS` dict in
   `scripts/gen_reference.py` so `make reference` emits `docs/reference/scan-predicate.schema.json` +
   `scan-predicate.md` (committed). The predicate's `scan_predicate_json_schema()` already exists but
   was never rendered; publishing it makes the contract readable to admission-policy authors **and**
   brings it under the CI drift gate — which is what makes the field description from change 1
   meaningful and verified. Sidebar position 4 (after `cli`).

3. **Precondition (documented, not built).** Max-age enforcement requires `HOUBA_ATTEST_SIGNER`:
   with no signer there is no signed predicate, so admission has nothing trustworthy to gate on.
   Admission reads the **signed** `attested_at`, never the unsigned `{prefix}.scan.timestamp`
   annotation (which stays, used only by `gc` for its local/temporal reap). Documented in the
   example README and the ADR.

4. **Worked example.** New `docs/examples/admission/` — a Kyverno policy (`verifyImages` +
   `attestations` of type `https://houba.dev/predicate/scan/v1` + temporal `conditions` that reject
   an `attested_at` older than the configured max-age) plus a README walkthrough, and a catalog entry
   in `docs/examples/README.md`. The exact JMESPath time syntax (`time_after` / `time_add` /
   `time_now_utc`) is verified at implementation — shape first.

5. **ADR 0033** (thin, follow-up to 0032): max-age = `attested_at`, enforced at admission; houba's
   role = present + signed + explicit contract; purely temporal, never correlation (the 0032
   boundary, restated at the freshness layer).

## Data flow (unchanged)

`attach` (signer enabled) → signed predicate carrying `attested_at` → admission reads the **signed
attestation**, checks `now − attested_at ≤ maxAge` → admit / deny. The field already flows; nothing
new happens in houba's runtime path.

## Boundary alignment (ADR 0032)

The check is **purely temporal** (age of a timestamp), never severity/content — currency ("vulnerable
today?") stays in Dependency-Track. Re-attaching an old report resets the clock; this risk is
**accepted**, mitigated by CI discipline (always scan-then-attach) and explicitly **not** houba's to
solve (non-goal).

## Testing

No new domain *logic* (the field description is prose; the generator change is config). The contract
is held two ways: (1) a unit test in `tests/unit/domain/scan/test_attestation.py` asserts
`attested_at` carries the freshness description; (2) the `make reference` drift gate now covers the
**published** `scan-predicate` schema/docs, so the rendered contract cannot drift from the model. The
Kyverno example is illustrative YAML, outside the pytest suite (as are the other `docs/examples/`).

## Non-goals

- An audit-side freshness tier (locus decided producer-side).
- A scanner report-time field in the predicate (clock decided = attach-time).
- Scheduling re-scans / re-attaches (cadence is an ops/CI concern).
- Any vulnerability correlation (Dependency-Track's job; the 0032 boundary).

## Architecture sync

- **No C4 change.** Consistent with ADR 0032: the admission controller stays the abstract
  "observability stack" consumer; modeling it would betray the portable, tool-agnostic stamp thesis.
- This spec is mirrored thin as **ADR 0033** (per the spec↔ADR convention).
- The Kyverno example satisfies "examples stay in sync with specs."
