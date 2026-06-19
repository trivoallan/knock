# 39. SBOM coverage backfill in reconcile

Date: 2026-06-19

## Status

Accepted. Fulfils the deferred consequence in [ADR 0034](0034-unify-sbom-on-syft.md), whose
Consequences already foresaw this: "images already rebuilt under 0029 carry an index-attestation
SBOM, not a referrer one; the future audit dimension (and optional backfill) reconciles them."
This ADR is that backfill.

## Context

`reconcile` attached SBOM referrers only on the import/rebuild path. An already-placed,
digest-stable image that lacked an SBOM referrer — from a partial/failed import, churn from an
earlier run, or placement before SBOM coverage was complete — was never re-covered: the only code
that attaches an SBOM was the rebuild path, and the 7-day stability window keeps a stable image
from ever being rebuilt. Rebuilt-variant images therefore showed zero discoverable SBOM referrers
on the digest their tag resolves to, so Dependency-Track and the blast-radius SBOM view found
nothing.

The originally-suspected cause — `regctl image mod` on an OCI index producing a digest that
diverges from the tag's resolved digest — was refuted end-to-end on Zot: `image mod` re-points
the tag, and the SBOM lands on exactly the digest `image digest <tag>` returns.

## Decision

`reconcile` self-heals SBOM coverage, mirroring the existing signature backfill (`to_sign`). A
kept digest missing any required SBOM referrer is routed to a `to_sbom` backfill that scans the
**live** digest with syft and attaches the missing referrers — no rebuild. Detection keys on SBOM
referrer presence (by media type), so it heals once and then converges (no duplicate referrers,
despite syft's non-deterministic output). One unfiltered referrer probe per existing tag now feeds
both coverage signals (signature + SBOM). Scans (`houba attach`, external/upstream) are out of
scope — houba cannot regenerate them.

## Consequences

- SBOM coverage is no longer import-only; images placed before coverage was complete are healed on
  the next reconcile.
- A new `"sbom"` operation kind appears in the report when a backfill runs.
- The change keys on the SBOM referrer, not its signed attestation; an image whose referrer is
  present but whose signed SBOM attestation is missing is not separately detected (same granularity
  as the signature backfill, which keys on the transform attestation).
- No new port/adapter and no policy-schema field, so the C4 model and `docs/reference/` are
  unaffected.

Full design spec:
[2026-06-19-sbom-coverage-backfill-design.md](../../superpowers/specs/2026-06-19-sbom-coverage-backfill-design.md)
