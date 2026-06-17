# Sign the SBOM — the trust tier — design

*Status: design. Roadmap item: *Now* → "Sign the SBOM under houba's identity (cosign) — the trust
tier, sequenced like stamp-then-sign" (ADR 0029, P1). Closes the gap named in
[explanation/sbom.md § "Presence, not yet trust"](../../explanation/sbom.md). Date: 2026-06-17.*

## Why (the gap, and why now)

houba already attaches a package-level SBOM to **every** placed digest — copy and rebuild alike — as
a raw OCI referrer. Its *presence* answers the blast-radius query. But the SBOM is attached
**unsigned**: nothing binds it to houba's identity, so a downstream admission controller cannot
*require* a trustworthy SBOM the way it can already require a signed transform attestation or a signed
scan result. That is the difference between "an SBOM is present" and "houba asserts this SBOM".

The precedent is already in the tree. `houba attach` attaches each scan result **both** as a raw
SARIF referrer **and** as a signed in-toto attestation (`https://houba.dev/predicate/scan/v1`), gated
by the single `HOUBA_ATTEST_SIGNER`. The SBOM is the one placed artifact still missing its signed
twin. This spec adds it, with the same shape.

Goal: **when signing is configured, every SBOM houba attaches also gets a signed in-toto attestation
under houba's identity, verifiable downstream with stock `cosign verify-attestation`.**

## What it is not (scope)

- **No new config knob.** SBOM-signing rides the existing `HOUBA_ATTEST_SIGNER` (the same identity
  that already signs transform + scan). Signing on ⇒ transform, scan, *and* SBOM are signed together;
  signing off ⇒ presence only. "The label is the product": everything signs as one.
- **Placement-time only.** The SBOM is signed in the same step it is generated — the syft bytes are
  already in hand, so there is **zero extra scan**. Images placed *before* signing was enabled are not
  retro-signed. Backfill of already-placed tags is deferred until a real signal demands it.
- **No `audit` "signed-SBOM" tier.** The roadmap's audit item is presence-only ("has SBOM", P0.5).
  A signed-SBOM coverage tier is a separate, later item; not built here.

## Mechanism — sign-as-predicate, reuse the attestor untouched

cosign's idiomatic signed SBOM is an in-toto attestation whose **predicate is the SBOM** and whose
`predicateType` is the canonical document type. houba's `AttestorPort.attest(subject_ref, statement)`
already signs an arbitrary in-toto Statement via `cosign attest --type <predicateType> --predicate
<predicate.json>`. So signing the SBOM needs **no port or adapter change** — only a pure domain
function that wraps the SBOM bytes as that Statement.

Two alternatives were rejected:

- **Sign the existing referrer in place** (`cosign sign <sbom-referrer-digest>`): avoids duplicating
  the SBOM, but needs the referrer digest discovered and a new `cosign sign` adapter path, and
  `cosign verify` over an artifact referrer is a clumsier downstream story than
  `verify-attestation --type spdxjson`. More surface, less idiomatic.
- **`cosign attest` reading the syft file directly** (shorthand `--type spdxjson`): marginally more
  byte-faithful, but needs a new port/adapter method to pass a raw file + shorthand instead of a
  built Statement. Not worth the surface.

The chosen approach re-serializes the SBOM into the signed predicate; the **byte-exact** original
still lives in the raw referrer, so nothing is lost.

## Design

### 1. Domain — one pure function (`houba/domain/sbom.py`)

```python
SBOM_PREDICATE_TYPES = {
    "spdx-json":      "https://spdx.dev/Document",   # cosign shorthand: spdxjson
    "cyclonedx-json": "https://cyclonedx.org/bom",   # cosign shorthand: cyclonedx
}

def build_sbom_statement(
    subject_name: str, subject_digest: str, sbom: SbomDocument
) -> dict[str, Any]:
    ...
```

Returns the in-toto v1 Statement:

- `_type`: `https://in-toto.io/Statement/v1`
- `subject`: `[{"name": subject_name, "digest": {"sha256": <hex of subject_digest>}}]`
- `predicateType`: `SBOM_PREDICATE_TYPES[sbom.format]`
- `predicate`: `json.loads(sbom.content)`

An unrecognized `sbom.format` raises `UnknownFormatError` (existing `DomainError` leaf → exit 1).
Fully `mypy --strict`; counts toward the ≥ 90 % `houba.domain` coverage bar. The canonical
`predicateType` is what lets a downstream `cosign verify-attestation --type spdxjson|cyclonedx`
resolve and match for free.

### 2. Use case — three lines (`houba/use_cases/reconcile.py`)

Inside the existing per-format SBOM loop in `_do_import`, immediately after `registry.put_referrer`:

```python
if attestor is not None:
    attestor.attest(
        placed,
        build_sbom_statement(f"{plan.dest_repo}:{w.out_tag}", out_digest, d),
    )
```

- **Per-format**: SPDX *and* CycloneDX (when both configured) each get a raw referrer **and** a
  signed attestation, on the same subject digest. cosign attaches each as its own referrer — no
  collision with the transform attestation already on that digest.
- **Inside the `try`**: a signing failure fails the operation, the same no-silent-gap rule that
  already governs SBOM generation and transform-signing.
- **Gated by `attestor is not None`**: rides `HOUBA_ATTEST_SIGNER`; no new wiring in `cli/_di.py`
  (the attestor is already constructed and passed in).

### 3. Failure semantics

Identical to the surrounding code: generation, raw attach, and signing all sit inside the operation's
`try`, so any failure marks the op failed rather than leaving a silently half-covered image.

## Test plan (TDD, one behavior per commit)

1. **Domain unit** (`tests/unit/domain/test_sbom.py`): `build_sbom_statement` for `spdx-json` →
   `https://spdx.dev/Document` and `cyclonedx-json` → `https://cyclonedx.org/bom`, asserting subject
   name/digest and that `predicate` round-trips the SBOM JSON; unknown format → `UnknownFormatError`.
2. **Use-case** (`tests/unit/use_cases/test_reconcile*.py`): with a `FakeAttestorPort`, assert one
   `attest` call is journaled **per SBOM format** with the canonical `predicateType` and the placed
   subject; with `attestor=None`, assert **no** `attest` call (presence only).

The `FakeAttestorPort` already journals `attest` calls — no fake change needed.

## Docs & specs in the same change (CLAUDE.md mandate)

- **`docs/explanation/sbom.md`** — rewrite the "Presence, not yet trust" section: the trust tier now
  exists; keep the presence-vs-trust framing, point at the same signer as the attestations doc.
- **`docs/explanation/attestations.md`** — add the two SBOM predicate types to the signer's coverage
  list (transform, scan, **SBOM**).
- **`docs/examples/attested/redis.yml`** walkthrough — show the signed SBOM and a
  `cosign verify-attestation --type spdxjson <image>` verification line.
- **Reference docs** — **no new field** (no new env var) ⇒ no `make reference` drift.
- **ADR 0029** — extend to record the signing tier (mirroring this spec); add a thin standalone ADR
  only if 0029 is frozen.
- **C4** — **no structural change** (no new port/adapter). The attestor's Component note gains
  "+ SBOM predicates"; refresh the Mermaid export only if that note changes.
- **`docs/roadmap.md`** — move "Sign the SBOM" from *Now* to *Delivered*.

## Net change

One pure domain function, three call-site lines, two test additions (no new fake), and the doc sync.
No new port, adapter, config var, or CLI surface.
