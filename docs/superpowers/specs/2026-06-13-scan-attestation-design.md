# Scan attestation — design (sign the `knock attach` scan referrer)

> **Status:** pre-implementation design, all forks resolved (§2, §10). Realizes the deferred
> signing seam (§11) of the attach-scan spec, now that the `AttestorPort` + `cosign` adapter
> landed on `main` (PR #49, SLSA attestation). The terminal step after this spec is `writing-plans`.

## 1. Context & motivation

`knock attach` (PR #42) ingests an upstream scan report and attaches it as a portable OCI
**referrer** on the image's digest, with an `io.knock.scan.*` annotation summary. That referrer is
**unsigned** — useful for a query, not for *enforcement*.

PR #49 delivered the heavy, signed provenance layer for the rebuild path: a generic
**`AttestorPort`** that signs an in-toto Statement (DSSE, via `cosign`) and attaches it as a
referrer, plus `AttestSettings` (`KNOCK_ATTEST_*`, off by default) and DI wiring
(`Container.attestor: AttestorPort | None`). The attach-scan spec explicitly reserved signing as a
future seam (§11) precisely because that port did not exist yet.

It exists now. This spec **signs the scan result**: knock emits a signed in-toto attestation whose
subject is the image digest and whose predicate carries the normalized scan summary. That turns
"this image was scanned" from a queryable annotation into a **cryptographically verifiable** fact —
what lets a downstream admission controller *require* a signed scan, closing the coverage-gate loop
the roadmap cares about (*coverage gates value*).

knock remains a **stamper, not a scanner**: the scan still runs upstream and is ingested. The
attestation is knock **vouching** "this scan result, for this image digest, was attached at time T",
recording the upstream scanner's identity — it is not a claim that knock performed the scan.

## 2. Decisions taken (the load-bearing forks)

| Fork | Decision | Why |
|---|---|---|
| **Predicate content** | **A knock scan predicate** — `https://knock.dev/predicate/scan/v1`, a pure-domain builder mirroring #49's transform predicate. | Carries knock's normalized value-add (the `io.knock.scan.*` summary); idiomatic (sibling of `TransformPredicate`); JSON Schema derived & frozen at `/v1`. Not cosign's generic vuln type, which drops the normalized summary; not the raw SARIF, which isn't an in-toto predicate. |
| **Relationship to the unsigned referrer** | **Additive** — always attach the raw SARIF referrer; *also* attach a signed attestation when a signer is configured. The predicate references the report referrer digest. | The raw report stays queryable (the `attach` value), and signing adds verifiability on top — mirrors #49 (signed attestation *alongside* the annotation stamp), not a replacement. |
| **Trigger** | **Config-driven, off by default** — sign iff `KNOCK_ATTEST_SIGNER` is set (the already-injected `attestor` is non-`None`). No new flag, no new env var. | Parity with #49's rebuild path; empty signer ⇒ no attestation (mirrors empty `KNOCK_LABEL_PREFIX` ⇒ no labels). Purely additive, safe behind config. |
| **Signing-failure semantics** | **Fail the attach (exit 2).** Scan findings still exit 0; a signing failure is a `CosignError` (`AdapterError` → exit 2) that propagates. | No silent coverage gap — exactly #49's "inside the try" stance. "Found vulns" (informational, exit 0) and "couldn't sign" (infra error, exit 2) are different outcomes. |
| **Port reuse** | **Reuse `AttestorPort` / `CosignAdapter` / `AttestSettings` / `FakeAttestor` unchanged.** `attest(subject_ref, statement: dict)` is already generic. | The novel work is a *pure domain* statement builder; signing + attaching is the unchanged I/O port. Minimal surface. |

## 3. Scope (v1)

**In:**
- `knock/domain/scan/attestation.py` (pure): a `ScanPredicate` Pydantic model + `build_scan_statement(...)` returning the in-toto Statement dict, and `scan_predicate_json_schema()`.
- Wire `attestor: AttestorPort | None` into `attach_scan` (use case) and the `attach` CLI command; record the result on `ScanOutcome`; render it.
- The published scan-predicate JSON Schema; a signed `docs/examples/` walkthrough variant; a short ADR; the C4 rationale note.

**Out / deferred:**
- **Verification / admission** — knock produces the attestation; consuming it is downstream (per the roadmap and #49's scope).
- **New scanner formats** — SARIF remains the only v1 format; signing applies to it.
- **Signing the copy/no-scan paths** — attestation attaches only where `attach` runs.
- **Any change to the `AttestorPort` / cosign trust models** — reused as-is (keyless / kms / key).

**Depends on:** the unified `put_referrer` (PR #52). `attach_scan` calls
`registry.put_referrer(subject, SCAN_RESULT_ARTIFACT_TYPE, annotations, blob=report_bytes,
media_type=mapper.report_media_type)` and uses the returned referrer digest as the predicate's
`report_digest`. This spec assumes #52 has merged.

## 4. The scan predicate (`https://knock.dev/predicate/scan/v1`)

Pure-domain, `mypy --strict`, ≥ 90 % coverage. A Pydantic model with `extra="forbid"` so its JSON
Schema is derived (never hand-written) and frozen as public API at `/v1` — exactly the
`TransformPredicate` pattern (`knock/domain/attestation.py`).

```python
# knock/domain/scan/attestation.py
SCAN_PREDICATE_TYPE = "https://knock.dev/predicate/scan/v1"
# in-toto Statement type is reused from domain/attestation.py: "https://in-toto.io/Statement/v1"

class Scanner(BaseModel):          # extra="forbid"
    name: str                      # the UPSTREAM scanner (from the report), e.g. "trivy"
    version: str                   # "" if the report doesn't carry it

class ScanPredicate(BaseModel):    # extra="forbid"
    scanner: Scanner
    format: str                    # "sarif"
    summary: dict[str, str]        # the io.knock.scan.* facts (vuln.critical, …), prefix-less keys
    report_digest: str             # digest of the raw SARIF referrer this attestation vouches for
    attested_at: str               # ISO-8601, when knock attached/signed (clock port)
    builder_id: str                # KNOCK_ATTEST_BUILDER_ID — knock as the attester/ingester

def build_scan_statement(
    *, subject_name: str, subject_digest: str,
    scanner_name: str, scanner_version: str, format: str,
    summary: dict[str, str], report_digest: str, attested_at: str, builder_id: str,
) -> dict[str, Any]:
    # returns {"_type": STATEMENT_TYPE, "subject": [{"name", "digest": {algo: value}}],
    #          "predicateType": SCAN_PREDICATE_TYPE, "predicate": ScanPredicate(...).model_dump()}
```

The subject is the **image digest** (the scanned artifact), shaped via the same `_subject_digest`
helper convention as the transform statement. The predicate is **honest**: `scanner` records the
upstream tool; `builder_id` records knock as the attester.

## 5. Architecture — wiring (mirrors #49's rebuild path)

```
cli/attach.py ─ passes container.attestor ─▶ use_cases/attach.py
                                              ├─ registry.put_referrer(...) → report referrer digest   (always)
                                              ├─ if attestor: build_scan_statement(...) [pure]
                                              └─        attestor.attest(subject, statement) → AttestationRef   (signer configured)
domain/scan/attestation.py (pure)  ─ build_scan_statement
ports/attestor.py (unchanged)      ─ AttestorPort.attest(subject_ref, statement) -> AttestationRef
adapters/cosign_cli.py (unchanged) ─ cosign attest --type <predicateType> --predicate <file> …
```

- **`use_cases/attach.py`** — `attach_scan(…, attestor: AttestorPort | None = None)`. After the
  (always-performed) `put_referrer`, if `attestor is not None`: build the scan statement (subject =
  `pin_to_digest(image_ref, info.digest)`, `report_digest` = the returned referrer digest,
  `attested_at` = `clock.now().isoformat()`, `builder_id` from config) and call
  `attestor.attest(subject, statement)`. Add the result to the outcome.
- **`ScanOutcome`** gains `attestation: AttestationRef | None = None` (frozen). `render_scan_outcome`
  prints the attestation's `predicate_type` + `referrer_digest` when present (both `text` and `json`).
- **`cli/attach.py`** — pass `container.attestor` and `container.settings.attest_builder_id` into
  `attach_scan`. No new CLI flag.
- **`AttestorPort` / `CosignAdapter` / `FakeAttestor` / `AttestSettings`** — unchanged.

## 6. Config

**No new config.** Reuse `KNOCK_ATTEST_*` (`attest_signer`, `attest_builder_id`, trust-model fields)
and the existing `Container.attestor` wiring (`CosignAdapter(settings.attest) if settings.attest_signer
else None`). Off by default.

## 7. Error model & exit codes

- Scan findings remain **informational → exit 0** (unchanged).
- When signing is enabled and `cosign` fails, `CosignError` (existing, `AdapterError`) propagates out
  of `attach_scan` → the CLI exits **2**. The raw referrer has already been attached, but the command
  reports failure rather than leaving an unsigned-but-claimed-signed gap — consistent with #49.
- No new error type.

## 8. Testing

- **Unit / domain (≥ 90 %):** `build_scan_statement` — Statement shape (`_type`, subject digest,
  `predicateType`), predicate fields (scanner, summary, `report_digest`, `attested_at`, `builder_id`),
  and `scan_predicate_json_schema()` derivation.
- **Use case (`FakeAttestor`):** attestor present ⇒ `attestor.attested` holds the statement with the
  correct subject (`repo@digest`) and `report_digest` equal to the referrer digest; attestor `None` ⇒
  no attestation, raw referrer still attached, `outcome.attestation is None`; `FakeAttestor(fail=True)`
  ⇒ `CosignError` propagates (and the raw referrer was still attached first).
- **CLI integration:** with `KNOCK_ATTEST_SIGNER=keyless` and the existing fake-bin
  `tests/fake-bins/cosign` (shipped by #49) on PATH, `knock attach` signs — exit 0, attestation
  rendered. The `CosignAdapter` is reused unchanged, so **no new adapter test** is needed.

## 9. Cross-cutting sync obligations (CLAUDE.md — same change)

- **JSON Schema** — publish `scan_predicate_json_schema()` (derived), alongside the existing
  `transform_predicate_json_schema` and the `io.knock.scan.*` annotation vocabulary.
- **`docs/examples/`** — add a signed variant to the `scan/` walkthrough: set `KNOCK_ATTEST_*`, show
  the resulting signed attestation referrer next to the raw report referrer.
- **C4 / `workspace.dsl`** — #49 already models the *Signing service* / *Transparency log* external
  systems and the knock→signer edge; scan-signing **reuses** them. No new model element — add one
  rationale sentence in `docs/architecture/README.md` that the signing edge now also covers `attach`.
- **ADR** — a short decision record (sibling of ADR 0006) capturing the scan-predicate type and the
  additive/config-driven/fail-on-signing-error decisions.

## 10. Resolved decisions (carried into `writing-plans`)

- **Predicate type → `https://knock.dev/predicate/scan/v1`** — project-branded vanity URI, frozen at
  `/v1`, derived JSON Schema; same convention as the transform predicate.
- **Additive, config-driven, off by default; signing failure → exit 2.** (§2.)
- **`AttestorPort` reused unchanged** — only a pure domain builder + use-case/CLI wiring are added.
- **Builds on PR #52** (unified `put_referrer`); `report_digest` is the digest that call returns.
