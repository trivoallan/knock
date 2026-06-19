# SBOM coverage backfill in reconcile — design

*Status: design. Closes the gap deferred by [the sign-the-SBOM spec](2026-06-17-sign-sbom-design.md)
("Backfill of already-placed tags is deferred until a real signal demands it") — the signal has now
arrived (see Evidence). ADR 0039. Date: 2026-06-19.*

## Why (the gap, and the signal)

A rebuilt variant in the reference demo (`demo/debian:bookworm-slim-eu` / `-us`) shows **zero**
SBOM/scan referrers on the digest its tag resolves to, so `scripts/publish-sbom.sh` (→
Dependency-Track) and the blast-radius SBOM/scan view find nothing for rebuilt images. The original
report blamed the OCI **index** shape — the hypothesis being that `regctl image mod` on an index
produces a digest that diverges from the one the tag finally resolves to, stranding the SBOM on a
different digest.

**That hypothesis is refuted by direct evidence.** A faithful end-to-end reproduction — the real
`houba reconcile` rebuild path, a real `buildkitd` producing the provenance index, real `syft`,
against Zot v2.1.17 (the demo registry) — placed both variants as OCI indexes and the SBOM landed on
exactly the digest the tag resolves to, discoverable via `regctl artifact list <tag>`. `regctl image
mod --replace` *does* change the digest (push → annotated), but it **re-points the tag** onto the new
digest; `image digest <tag>` returns precisely the `out_digest` the SBOM is attached to. Confirmed in
isolation on both `registry:2` and Zot, single- and multi-pass.

### The real root cause

`reconcile` attaches SBOM referrers **only on the import/rebuild path** (`_do_import`). It has **no
coverage backfill** for an already-placed, digest-stable image. There *is* a backfill for the
**signature** (`to_sign` → `_do_sign`, which re-signs a kept digest without rebuilding) — but nothing
equivalent for the SBOM.

Cluster evidence: both live variant digests carry 0 referrers and their stamp `created` is
`2026-06-17`, two days stale; three reconciles ran on 2026-06-19 and left those digests untouched
(`created` unchanged) — i.e. they **skipped** the variants as digest-stable (7-day stability window).
So whatever first left the live digest uncovered (a partial/failed import, churn from an earlier
`make demo`, or placement before SBOM coverage was complete), the stability window now **guarantees
reconcile will never heal it**: the only code that attaches an SBOM is the rebuild path, and the
variant is never rebuilt. The SBOM/scan that *do* exist sit on the prior digest the tag pointed to
before it last churned.

Goal: **on every reconcile, a kept (not-rebuilt) placed image that is missing any required SBOM
referrer gets it (re)attached on the live digest — no rebuild — exactly the way `to_sign` backfills a
missing signature.** Coverage becomes self-healing instead of import-only.

## What it is not (scope)

- **No scan backfill.** houba does not run scanners; scan results come from `houba attach` (external,
  upstream). houba cannot regenerate a scan, so an externally-attached scan orphaned by a past tag
  move is out of scope. In the demo, the SCAN column is healed by re-running `make scan` against the
  now-stable live digest — no houba code. (Per [ADR 0032](../../architecture/decisions/0032-attach-is-scan-provenance-not-a-store.md):
  attach is scan provenance, not a store.)
- **No import-atomicity change.** Making `_do_import` refuse to "place" an image whose SBOM/sign step
  failed (to prevent *new* orphans) is a separate hardening, not needed here: the backfill heals the
  gap regardless of how it arose, and converges.
- **No new config knob.** The backfill rides the existing `HOUBA_SBOM_FORMATS` /
  `HOUBA_ATTEST_SIGNER` exactly as the import path does. SBOM off ⇒ nothing to backfill.
- **No policy-schema field, no `docs/reference/` regen.** `sbom_covered` is internal reconcile
  state, not a `MirrorPolicy` field.
- **Detection keys on the SBOM *referrer*, not its signed twin.** `sbom_covered` is true when every
  required SBOM media type is present as a referrer — that is exactly what `publish-sbom.sh` and the
  blast-radius view read. When the backfill fires, `_attach_sbom` also re-signs the SBOM (if signing
  is on), so a healed image is both present and signed. But an image whose referrer is present while
  only its *signed attestation* is missing is **not** separately detected — the same granularity as
  today's signature backfill, which keys on the transform attestation. Closing that finer gap is a
  later concern, not this spec.

## Mechanism — mirror the signature backfill, one probe, shared attach

### Domain (`houba/domain/reconcile.py`)

- `MirrorArtifact` gains `sbom_covered: bool = True` — does the kept digest already carry every
  required SBOM referrer? Default `True` keeps SBOM-less configs and existing call sites unchanged.
- `_classify` is narrowed to decide only rebuild-vs-keep: it returns `"import" | "update" | "keep"`.
  The `"skip"` / `"sign"` split is removed — coverage is now **orthogonal** to the keep decision.
- `reconcile_variant`: for a `"keep"` decision, derive the backfills **independently**:
  - append to `to_sign` if `not mirror.attested`;
  - append to `to_sbom` if `not mirror.sbom_covered`.
  A fully-covered kept image lands in neither (the old `skip`). An image may be in **both**.
- `VariantReconcile` gains `to_sbom: list[str] = field(default_factory=list)`.

Signature-backfill behavior is unchanged: `to_sign` is still driven by `attested`, computed exactly
as before.

### Ports (`houba/ports/registry.py` + adapter + fake)

- `list_referrers(image_ref, artifact_type: str | None = None)`: when `artifact_type is None`, return
  **all** referrers — one probe yields every `artifactType` present on the digest. Backward
  compatible (existing callers pass a concrete type).
- `RegctlAdapter.list_referrers`: omit `--filter-artifact-type` when `artifact_type is None`.
- `FakeRegistryPort.list_referrers`: return all seeded referrers when `artifact_type is None`.

### Use-case (`houba/use_cases/reconcile.py`)

- In `_apply_plan`'s per-existing-tag loop, replace the cosign-only `attested` probe with **one
  unfiltered** `list_referrers(tag)`; let `present = {r.artifact_type for r in refs}`. Then:
  - `attested = attestor is None or COSIGN_ATTESTATION_ARTIFACT_TYPE in present`;
  - `missing_sbom = [f for f in sbom_formats if media_type_for(f) not in present]` (empty when no
    `sbom_generator` / no formats); `sbom_covered = not missing_sbom`;
  - record `missing_by_tag[out_tag] = missing_sbom` for the backfill stage.
- Pass `sbom_covered=…` into `to_mirror_artifact` → `MirrorArtifact`.
- **Extract** the SBOM block currently inline in `_do_import` into a shared helper
  `_attach_sbom(out_digest, out_tag, formats, …)` that does, per format: `sbom_generator.generate` →
  `registry.put_referrer` → (if `attestor`) `attestor.attest(sbom_statement)`. `_do_import` calls it
  with the full `sbom_formats`; the backfill calls it with only the missing subset. This guarantees
  import and backfill cannot drift.
- New `_SbomWork(variant, vplan, out_tag, src_tag, formats)` built from `vr.to_sbom` (mirroring how
  `_SignWork` is built from `to_sign`, using `out_to_src` for `src_tag`). New `_do_sbom(w)`: takes the
  **live** digest `out_digest = mirror_digests[w.out_tag]` (no rebuild) and calls `_attach_sbom`.
  Emits an `Operation` of kind `"sbom"`. Runs as its own stage after the `_do_sign` backfill, with the
  same executor/barrier and per-variant report reassembly as `to_sign` (`sbom_by_variant`).

### Reporting (`houba/ports/reporter.py` + report)

- Add `"sbom"` to `OperationKind` and `sbom: int = 0` to `Counts`; extend `_counts_of` /
  `_merge_counts` and the text/JSON report rendering to surface the new kind.

### Idempotency (no referrer bloat)

The backfill attaches only media types absent from the probe. Once attached, the next reconcile's
probe sees them → `sbom_covered = True` → no re-attach. The hourly cron therefore heals each gap
exactly once and then converges — even though syft output is non-deterministic, no duplicate referrer
is ever produced because presence (by media type) is checked first. Same convergence guarantee as
`to_sign`.

## Tests (TDD)

- **Domain unit** (`tests/unit/domain/`): a kept digest with `sbom_covered=False` appears in
  `to_sbom`; with `True` it does not; `to_sbom` and `to_sign` are independent (a kept digest that is
  both unsigned and uncovered appears in both); `import` / `update` decisions never populate
  `to_sbom`; an `update` (rebuild) does not.
- **Use-case unit** (`tests/unit/use_cases/`) — the bug's regression test: `FakeRegistryPort` seeded
  with a placed, digest-stable, stamped destination tag whose seeded referrers **lack** the SBOM
  media types ⇒ reconcile runs `_do_sbom`; assert `FakeSbomGenerator.calls` includes the **live
  destination digest** (not a rebuild), `FakeRegistryPort.artifact_referrers` records the missing-format
  referrers attached to that live digest, and a `"sbom"`-kind operation is reported. Converse: when the
  SBOM referrers are already seeded, `FakeSbomGenerator` is **not** called (converged, no bloat).
- **Adapter unit** (`tests/integration/`): `RegctlAdapter.list_referrers(ref)` (no type) omits
  `--filter-artifact-type` in the fake-bin argv log.

## Deliverables

- Code + tests above.
- **ADR 0039** (`docs/architecture/decisions/0039-sbom-coverage-backfill.md`) — thin, links here:
  "reconcile self-heals SBOM coverage on kept digests, mirroring the signature backfill."
- One line in the reconcile explanation doc noting coverage is now self-healing (not import-only),
  cross-linking the sign-the-SBOM spec's deferred-backfill note.
- No `docs/reference/` regen (no user-facing schema change). No C4 structural change (no new
  port/adapter; `list_referrers` gains an optional argument and reconcile gains a stage — neither
  shifts a layer boundary).
