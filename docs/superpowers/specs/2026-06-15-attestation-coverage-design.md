# Complete attestation coverage — design

*Status: design. Roadmap item: **Now → "Complete attestation coverage"** (closes the known
#49 / #53 gaps). Date: 2026-06-15.*

## Why

houba's value lands at incident time, and it flows through the **signed provenance attestation** —
*the label is the product*, and *coverage gates value*. The single-front-door mandate is now
confirmed, so a coverage hole is no longer theoretical: today only the **rebuild** path signs an
attestation. Images that houba **copies** (no transform) or **skips** (already mirrored, digest-stable)
carry the OCI/`io.houba.*` annotation stamp but **no signed attestation** — exactly the hole the
coverage audit surfaces. The mandating team cannot rely on a signed-coverage query while two of three
paths are unsigned.

Goal: **every image houba fronts carries a signed houba attestation**, computed idempotently so the
fleet is signed once, not re-signed every reconcile.

## The unifying rule

Replace the current signing trigger — *"is there a transform?"* (the `w.vplan.transform` guard at
`use_cases/reconcile.py` ~line 408) — with: **every image houba places or finds must carry a signed
houba attestation.**

| Case | Today | After |
|---|---|---|
| import/update via **rebuild** | signs | signs (unchanged) |
| import/update via **copy** | does not sign | **signs** (drop the `transform` guard) |
| **skip** (mirrored, stable) but unsigned | nothing | **sign-only op** (idempotent backfill) |

## 1. Domain — the plan carries the backfill (`domain/reconcile.py`)

The decision *"is this digest already attested?"* is **state passed in**, never inferred in the
domain — the exact mirror of the existing `transform_version` mechanism.

- `MirrorArtifact` gains `attested: bool`. Populated by the adapter at state-gathering time. Default
  is `True` (so a caller that does not wire the field never triggers a surprise re-sign storm; the
  real adapter always sets it explicitly).
- `VariantReconcile` gains `to_sign: list[str]`.
- `_classify` gains the `attested` input: when its decision is "skip" (image is up-to-date) **and**
  `not attested`, it returns `"sign"`. `reconcile_variant` routes `"sign"` tags into `to_sign`;
  `import`/`update` are unchanged.

The domain stays pure: it receives "is it signed?" and derives the plan.

## 2. The predicate — explicit discriminator (`domain/attestation.py`)

`build_transform_statement` already accepts `steps=[]` / `transform_version=""`, which is the copy
case. Rather than make consumers infer "copied" from `steps == []`, the predicate carries an explicit
boolean field **`transformed: bool`** (`True` for rebuild, `False` for copy/skip-backfill).

- **Same `predicate_type`, same schema** → one query at incident time (honors *the label is the
  product* / one-query thesis), but honest about hardened-vs-passed-through.
- No new builder: add a `transformed: bool` parameter to `build_transform_statement`. For copy and
  skip-backfill, callers pass `transformed=False`, `steps=[]`, `transform_version=""`.

## 3. Use case — wiring (`use_cases/reconcile.py`)

- **State gathering.** When building each `MirrorArtifact`, call
  `registry.list_referrers(dst_ref, COSIGN_ATTESTATION_ARTIFACT_TYPE)` and set
  `attested = len(refs) > 0`. (Port already exists — no new port/adapter.) Done for **all** mirrored
  tags (simpler than a skip-only second pass; in steady state most tags are skips anyway, so this is
  the backfill cost itself).
  - *ponytail: heuristic "a cosign attestation bundle exists ⇒ houba already signed this digest";
    sufficient for idempotence — we do not re-verify the signature. Tighten only if another tool is
    known to attach attestations to the same digests.*
- **Copy path.** Drop `and w.vplan.transform` from the signing guard (~line 408); on the copy branch
  sign with `transformed=False`.
- **Sign-only pass (`to_sign`).** For each backfill tag, resolve its current destination digest (via
  the `inspect` / `get_annotations` read already performed during gathering) and call
  `attestor.attest(dst@digest, statement)` with `transformed=False`. **No copy, no re-stamp** — the
  annotation stamp is already present (roadmap premise: skipped images already carry the houba stamp).

`COSIGN_ATTESTATION_ARTIFACT_TYPE` is the cosign v3 attestation-bundle media type the
`CosignAdapter` already produces; define it as one shared constant.

## 4. Cost & idempotence

One extra `list_referrers` read per already-mirrored tag at gathering. In steady state most tags are
skips, so this read *is* the backfill probe. Once a digest is signed it is never re-signed (digest is
immutable ⇒ `attested == True` forever after) — no KMS/Rekor storm, no unbounded referrer growth from
this feature.

## Out of scope (assumed)

- **Re-signing on predicate-schema bumps.** YAGNI while the schema is stable; the immutable digest
  makes a one-time signature durable. A schema migration is a separate, future concern.
- **Stamping/backfilling the annotation on images placed by another tool.** The roadmap premises that
  skipped images already carry the houba stamp; this design backfills the *signature* only.
- **Extending `houba audit` to a signed-vs-unsigned coverage tier.** A natural follow-up once all
  paths are signed (and explicitly listed apart on the roadmap), not part of this change.

## Testing (TDD)

- **Domain (`tests/unit/domain`, ≥ 90 %):** `_classify` returns `"sign"` on skip + unattested and
  nothing on skip + attested; `reconcile_variant` populates `to_sign`; `build_transform_statement`
  emits `transformed=True` for rebuild and `transformed=False` for copy with `steps=[]`.
- **Use case (fakes):** copy path signs (`transformed=False`); a skipped-but-unattested tag signs
  exactly once; a skipped-and-attested tag does not sign — assert via `FakeAttestor` journal and
  `FakeRegistry.list_referrers` seeded state.

## Docs to sync (same change)

- ADR mirror under `docs/architecture/decisions/` linking this spec.
- C4 model: **unchanged** — no new port, adapter, actor, or external system (reuses `RegistryPort`,
  `AttestorPort`, `CosignAdapter`).
- `docs/examples/`: refresh if a shown attestation now displays the `transformed` field.
- Roadmap: tick the *Now* "Complete attestation coverage" item when shipped.
