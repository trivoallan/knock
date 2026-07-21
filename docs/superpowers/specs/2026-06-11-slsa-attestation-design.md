# SLSA / in-toto attestation — design (roadmap ①, the heavy-provenance layer)

> **Status:** approved design, all open questions resolved (§7), pre-implementation. Builds
> on the provenance *annotation* stamp (`knock/domain/stamp.py`, v0.2.0) and the rebuild path
> (Phase 6, `buildkit_cli`). The terminal step after this spec is `writing-plans`.

## 1. Context & motivation

knock is a **stamper / single front door** for external OCI images. The roadmap's first
Phase-C item is *"the label is the product"* — freeze the provenance contract. Two layers:

1. **Cheap, scanner-readable facts** — OCI-standard annotations + `io.knock.*` lineage.
   **Already delivered** by `domain/stamp.py`: `org.opencontainers.image.source/revision/
   base.name/base.digest/created` plus `io.knock.{policy,import,variant,transform.steps,
   transform.version,owner.team}`. Cheap, unsigned, mutable-in-principle.
2. **Heavy, signed, verifiable provenance** — SLSA / in-toto **attestations**. This spec.
   The annotation is the index card; the attestation is the notarized record it points at.

The roadmap states the direction directly: *"Carry heavy provenance as SLSA / in-toto
attestations, not ad-hoc labels."* This makes the front door not just *stamped* but
*cryptographically verifiable*, which is what lets a downstream admission controller
**enforce** "only knock-built images run here" — closing the coverage-gate argument.

## 2. Decisions taken (the three load-bearing forks)

| Fork | Decision | Why |
|---|---|---|
| **Trust / signing model** | **Pluggable signer port, defer policy** | knock targets internal-CA / internal-mirror / often air-gapped orgs. Hardcoding Sigstore-keyless (public Fulcio + public Rekor) would bake in egress + public-log exposure those orgs reject. A signer **port** with keyless *and* KMS/key adapters keeps trust an org **configuration of a generic primitive** — the knock invariant. |
| **Build-provenance source** | **Both: BuildKit native base + knock transform predicate** | BuildKit already emits SLSA provenance (`attest:provenance`). Reuse it for the *build* facts (don't reimplement the SLSA schema); emit a **separate** `io.knock` predicate for the *hardening lineage* — the genuinely novel fact BuildKit can't know. Clean standard-vs-novel split, mirroring the annotation layer. |
| **SLSA level claimed (v1)** | **Build L2** | Signed provenance from a hosted build platform — honest and attainable for knock running `buildctl` in its runtime image. **L3** needs build-isolation / non-falsifiability guarantees knock does not yet make; claiming it would be over-claiming. L2 is the floor that still unblocks signature-based admission. |

## 3. Scope (v1)

**In:**
- **Enable BuildKit SLSA provenance** on the rebuild path: `buildctl ... --opt
  attest:provenance=mode=max`, attached by the builder as an OCI **referrer** at push.
- **A knock transform predicate** — pure-domain construction of an in-toto Statement whose
  subject is the output digest and whose predicate is the *resolved, ordered* hardening
  recipe (which policy/import/variant, which CA names, which mirror, the source digest, the
  builder id, timestamps).
- **A pluggable `AttestorPort`** that signs an in-toto Statement (DSSE) and attaches it as a
  referrer to the subject digest. **One adapter in v1** (`cosign`), configurable across the
  keyless / KMS / static-key trust models — so the *port* lands now and the second adapter,
  if ever needed, is additive.
- **Discovery via the OCI Referrers API**, stored alongside the image in the registry, with
  **automatic fallback to cosign's `sha256-<digest>.att` tag schema** on registries that don't
  yet serve the Referrers API (Q4). Nothing new in the manifest; verifiers walk referrers.
- **Config sub-block `AttestSettings`** (`KNOCK_ATTEST_*`), JSON-Schema-published like the
  rest. Attestation is **off by default** (empty signer ⇒ no attestation, mirroring empty
  `KNOCK_LABEL_PREFIX` ⇒ no labels).

**Out (deferred / explicitly not knock):**
- **Verification / admission policy.** knock *produces* attestations; *consuming* them
  (Kyverno/cosign-policy/admission) is downstream, per the roadmap's "knock stamps; it does
  not watch where its images run." A future `knock verify` is a candidate, not v1.
- **An internal transparency log deployment.** knock can *point at* a Rekor URL (config);
  standing one up is the org's infra, not knock's.
- **Multi-platform attestation fan-out** — follows the rebuild path's single-platform v1.
- **Attestation on the pure copy path (no rebuild).** v1 attaches the knock predicate only
  where there *is* a transform to attest. Copy-path provenance stays at the annotation layer
  until there's demand. (Resolved: Q3 — rebuild-only in v1, copy as fast-follow.)

## 4. Architecture — hexagonal placement

The pattern is the standard knock one: **port (Protocol + frozen dataclass) → fake → adapter
→ wire into `cli/_di.py`.** Predicate *construction* is pure domain (a sibling of `stamp.py`);
*signing + attaching* is I/O (an adapter, the only place retry lives).

```
domain/attestation.py   (pure)   build_transform_statement(facts) -> InTotoStatement
        │  no httpx / subprocess / os.environ — like stamp.py
        ▼
ports/attestor.py       (Protocol + dataclass)
        AttestorPort.attest(subject_ref, statement) -> AttestationRef
        ▲
adapters/cosign_cli.py  (subprocess; retry on transient via _Transient)
        sign DSSE (keyless | kms | key, per config) + attach as referrer
```

- **`domain/attestation.py`** — `build_transform_statement(...)` returns the in-toto
  **Statement** dict (`_type`, `subject: [{name, digest}]`, `predicateType`, `predicate`).
  Pure; fully `mypy --strict`; ≥ 90 % coverage. The predicate shape is a Pydantic model so
  its JSON Schema is *derived*, never hand-written, and published for editor/CI validation.
- **`ports/attestor.py`** — `AttestorPort` Protocol + a frozen `AttestationRef`
  (`{predicate_type, referrer_digest}`). Never imports from `adapters.*`. A journaling
  `FakeAttestor` (records `.calls.attested`) lives in `tests/fakes/`.
- **`adapters/cosign_cli.py`** — wraps `cosign attest` / `cosign sign` via `subprocess`.
  The trust model (`keyless` → Fulcio+OIDC; `kms` → `--key <kms-uri>`; `key` → static key)
  is selected from `AttestSettings`, so **the same port has one adapter, three configurations**.
  A private `_Transient(CosignError)` triggers tenacity retry on network/5xx; non-transient
  raises immediately. New CLI-tool adapter ⇒ new **fake-bin** (`tests/fake-bins/cosign`,
  `chmod +x`, branch on `FAKE_COSIGN_SCENARIO`, append argv to `FAKE_COSIGN_LOG`).
- **`ports/image_builder.py`** — extend `BuildRequest` with `provenance: bool = False`;
  `buildkit_cli` maps it to `--opt attest:provenance=mode=max`. BuildKit attaches its own
  SLSA provenance; knock does not reconstruct it.
- **`cli/_di.py`** — build the attestor from config; pass into the rebuild use case. Wiring,
  excluded from coverage.

### Two attestations, by design
1. **`https://slsa.dev/provenance/v1`** — emitted by **BuildKit**, attached by BuildKit. The
   *build* facts. knock's job is only to *enable* it (and ensure `builder.id` is meaningful).
2. **knock transform predicate** (`predicateType: https://knock.dev/predicate/transform/v1`)
   — emitted by **knock domain**, signed + attached by the **`AttestorPort`**. The *hardening
   lineage*. This is the novel artifact and the reason knock exists; it is to attestations
   what `io.knock.*` is to labels. **Standalone** by design (Q2): BuildKit's provenance is
   left untouched and knock never has to intercept or rewrite it.

## 5. Config — `AttestSettings` (`KNOCK_ATTEST_*`)

Single-underscore contract (own `env_prefix`), per the config invariant. Off by default.

| Var | Meaning | Default |
|---|---|---|
| `KNOCK_ATTEST_SIGNER` | `""` (off) \| `keyless` \| `kms` \| `key` | `""` |
| `KNOCK_ATTEST_KEY_REF` | KMS URI or key path (for `kms`/`key`) | `""` |
| `KNOCK_ATTEST_FULCIO_URL` | CA for keyless (blank ⇒ public Fulcio) | `""` |
| `KNOCK_ATTEST_REKOR_URL` | transparency log (**blank ⇒ no log entry**, the air-gapped path) | `""` |
| `KNOCK_ATTEST_BUILDER_ID` | URI identifying this knock builder (feeds both predicates) | `""` |

`KNOCK_ATTEST_SIGNER=""` ⇒ no signer constructed ⇒ no attestation attached. The annotation
stamp is unaffected and still ships. This makes attestation purely additive and safe to roll
out behind config, consistent with empty-prefix ⇒ no labels.

## 6. Cross-cutting sync obligations (CLAUDE.md, do not skip in the plan)

These are part of the *same change* as the implementing spec, not follow-ups:

- **C4 / `docs/architecture/workspace.dsl`** — this introduces, at context level, a new
  external system **Signing / Key service** (KMS *or* Fulcio) and, optionally, a
  **Transparency log** (Rekor), plus the **knock → signer** integration. The model must gain
  these in lockstep; a spec that shifts the context view is not done until `workspace.dsl`
  reflects it.
- **`docs/examples/`** — add a `MirrorPolicy` walkthrough showing an attested rebuild,
  marked *"requires the attestation path"* until it lands, so the design is documented now
  and becomes runnable when the feature ships.
- **Runtime image (`Dockerfile`)** — bundle `cosign` alongside `skopeo`/`buildctl`/`git`
  (separate infra task, called out so the plan budgets it).
- **JSON Schema** — publish the derived schema for the knock predicate and the new config
  block; validate inputs against it.

## 7. Resolved decisions (carried into `writing-plans`)

All four open questions are settled; the plan starts from these, not from options.

- **Q1 — predicate type URI → `https://knock.dev/predicate/transform/v1`.** A project-branded
  vanity URI (the convention SLSA itself follows with `slsa.dev`); needn't resolve, stays
  stable across repo moves, generic (no deploying-org reference). This is frozen public API —
  the `predicateType` and its Pydantic-derived JSON Schema are versioned at `/v1`.
- **Q2 — standalone knock predicate (two attestations).** BuildKit's `slsa.dev/provenance/v1`
  is left untouched; knock emits a *separate* transform predicate. Clean standard-vs-novel
  split, no interception/rewrite of BuildKit's output. Verifiers that only understand
  `slsa.dev/provenance` still get the build facts; knock-aware verifiers read both.
- **Q3 — rebuild-only in v1; copy path is a fast-follow.** v1 attests where there is an actual
  transform to describe (richest predicate, smallest surface). The known consequence is a
  temporary coverage gap for pure copies — pure-copy signing (minimal predicate: source
  digest, empty transform list) is a focused follow-up once the signer port is proven, and is
  what fully unlocks uniform admission enforcement ("coverage gates value").
- **Q4 — Referrers API with automatic tag-schema fallback.** cosign's default behaviour: use
  the OCI Referrers API where served, fall back to `sha256-<digest>.att` tags otherwise. No
  minimum-registry-version requirement forced now; works across Harbor versions out of the box.
