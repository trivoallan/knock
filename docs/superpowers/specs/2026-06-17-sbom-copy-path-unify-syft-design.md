# SBOM on both paths — unify generation on syft — design

*Status: design. Supersedes the **mechanism** of [2026-06-16-sbom-generation-design.md](2026-06-16-sbom-generation-design.md)
/ ADR 0029 (the value proposition — package-level blast-radius — is unchanged; only how the SBOM is
produced and attached changes). Roadmap item: closes the copy-path coverage gap that ADR 0029 left
as a non-goal. Date: 2026-06-17.*

## Why (the gap, and why now)

ADR 0029 generates an SPDX SBOM **on the rebuild path only**, via buildkit's native scanner, attached
at push as an image-index attestation manifest. It deliberately left two things open:

1. **The copy path (~1% of intake) carries no SBOM** — "no build to observe", deferred behind a
   `# ponytail:` until a volume signal.
2. **Format is SPDX-only** — buildkit's `attest:sbom` emits nothing else.

Two forces now make the deferred design the wrong shape:

- **CycloneDX is a hard requirement taking shape.** buildkit's SBOM frontend emits **only** SPDX.
  If a consumer needs CycloneDX, buildkit *cannot* produce it — you need syft (or trivy) regardless.
  So the moment CycloneDX is real, a standalone generator enters the picture for the rebuild path
  too; keeping buildkit's SPDX *alongside* it is pure redundancy.
- **buildkit forces two attachment mechanisms.** The rebuild SBOM lives as an image-index
  attestation manifest; a copy-path SBOM (a post-hoc document) can only be an OCI referrer. Two
  storage locations means the future `audit "has SBOM"` dimension must probe both, and the value the
  product sells — *one query answers blast-radius* — fractures across two shapes.

Unifying on a standalone generator (syft) for **both** paths removes the redundancy, collapses the
two mechanisms into one (OCI referrer), and makes CycloneDX a config flag rather than an
impossibility. It is *less* surface, not more.

Goal: **every image knock places — rebuilt or copied — carries a portable, package-level SBOM in the
org's chosen format(s) (SPDX and/or CycloneDX), attached uniformly as an OCI referrer.**

## Depth is already validated — same engine

The one real risk for SBOM coverage was *depth* (does the scanner see application-layer deps in
nested JARs, OS packages with purls, the runtime boundary). ADR 0029 retired it empirically against
`docker/buildkit-syft-scanner` — which **is syft**, packaged for buildkit. Standalone syft is the
same engine, so the depth findings and the documented bare-binary-middleware limit
([2026-06-16-sbom-generation-design.md](2026-06-16-sbom-generation-design.md) §"Empirical
validation" / §"Known coverage limit") carry over unchanged. What moves is *when* the scan runs
(post-push, against the placed digest) and *how it attaches* (referrer) — not the scanner's reach.

## The decision

**One tool, one mechanism, configurable formats.**

- Drop buildkit's `--opt=attest:sbom=true` (and `BuildRequest.sbom`). Keep `attest:provenance`.
- A new `SbomGeneratorPort` (driven by syft) scans the **placed image by digest** and returns one
  document per requested format.
- Each document is attached as an **OCI referrer** to the placed digest — copy and rebuild
  identical. The audit "has SBOM" dimension (separate follow-up) then has a single probe.
- The SBOM-generation step is **common to both paths** — it runs after the digest is known, so the
  `copy`-vs-`build` branch only decides how the image is *placed*, not whether it gets an SBOM.

Cost accepted (explicitly, during design): the rebuild path (~99% of intake) now does a post-push
scan (syft pulls the placed layers) instead of buildkit's free in-build attestation. This is the
price of one tool / one mechanism / CycloneDX-anywhere, and is acceptable for a front-door tool's
volume.

## Architecture (follows the house pattern: port → fake → adapter → wiring)

### 1. Port — `knock/ports/sbom.py`

```python
@dataclass(frozen=True)
class SbomDocument:
    format: str        # syft output name, e.g. "spdx-json" / "cyclonedx-json"
    media_type: str    # "application/spdx+json" / "application/vnd.cyclonedx+json"
    content: bytes      # the serialized SBOM

class SbomGeneratorPort(Protocol):
    def generate(self, image_ref: str, formats: list[str], *, tls_verify: bool = True) -> list[SbomDocument]:
        """Scan image_ref (a digest-pinned ref) and return one document per format. One scan, N outputs."""
```

`typing.Protocol` + frozen data model, never imports adapters. Stays `mypy --strict`.

### 2. Adapter — `knock/adapters/syft_cli.py` (`SyftAdapter`)

- Drives syft once with multiple `-o <fmt>=<path>` outputs (one scan, N files), reads them back.
- **Lazy binary resolution** (the buildkit/git pattern, per repo convention) — not eager.
- Raises `SyftError` (new leaf under `AdapterError` → exit 2).
- **Registry auth/TLS:** syft must pull the placed image from the destination registry. The adapter
  maps the destination `RegistryConfig` → syft auth (env: `SYFT_REGISTRY_AUTH_*`) and the insecure /
  TLS flag — mirroring the existing regctl session and the buildkit-push `tls_verify` handling
  (#127) and the plain-HTTP local demo (#131). Exact wiring is an implementation detail for the plan.

### 3. Domain — `knock/domain/sbom.py` (pure)

- `FORMAT_MEDIA_TYPES: dict[str, str]` — the `spdx-json`/`cyclonedx-json` → media-type mapping, and a
  helper to map a format to its referrer artifact type.
- `build_sbom_annotations(*, prefix, subject_digest, fmt, tool, tool_version, timestamp)` — the
  referrer's annotations (mirrors `domain/scan/summary.build_scan_annotations`). No I/O.

### 4. Config — `knock/config.py`

- New `KNOCK_SBOM_FORMATS`: JSON list of syft format names. Default `["spdx-json"]` (SPDX parity);
  validated against the allowed set `{"spdx-json", "cyclonedx-json"}`; **non-empty** (always-on
  coverage — the knob chooses *which* formats, never *whether*). Global, not per-policy: the format
  is an org / observability-stack decision, not a per-image one. Triggers `make reference`.

### 5. Wiring — `knock/use_cases/reconcile.py`

- Remove `sbom=True` from `_build_variant` / `BuildRequest`.
- In `_do_import`, after `out_digest = registry.annotate(...)`, a **common block** (both branches):
  `docs = sbom_gen.generate(f"{plan.dest_repo}@{out_digest}", sbom_formats, tls_verify=plan.config.tls_verify)`
  then `registry.put_referrer(dest@out_digest, artifact_type(d.format), build_sbom_annotations(...), blob=d.content, media_type=d.media_type)` per document.
- **Inside the `try`** ⇒ a generation/attach failure fails the operation (no silently-uncovered
  image), exactly as signing does today. **Fail-hard.**
- Thread `SbomGeneratorPort` + `sbom_formats` through `reconcile_policies` and `cli/_di.py`.

## Out of scope (v1)

- **SBOM signing** (cosign over the SBOM). Stays P1 / follow-up — parity with today's rebuild path,
  whose SBOM is also unsigned (only the stamp/transform statement is signed). The existing stamp
  attestation is untouched.
- **Backfill** of already-mirrored images. Non-goal (per ADR 0029). **Transition note:** images
  already rebuilt under ADR 0029 carry an *index-attestation* SBOM, not a referrer one; the future
  `audit "has SBOM"` dimension (and an optional backfill) reconciles the two mechanisms — not v1's
  problem.
- The **`audit "has SBOM"` dimension** — separate follow-up; now simpler (one referrer probe instead
  of index inspection + referrer).
- Formats beyond SPDX / CycloneDX; the blast-radius **query engine** (downstream, standing non-goal).

## Testing (TDD)

- **Adapter (`tests/integration`, new fake-bin `syft`):** `generate(ref, ["spdx-json","cyclonedx-json"])`
  ⇒ argv carries both `-o spdx-json=…` and `-o cyclonedx-json=…`; returns two `SbomDocument`s with
  the right media types and the fake-bin's bytes. Auth/insecure flag asserted from `tls_verify`.
  `SyftError` on a failing scenario (`FAKE_SYFT_SCENARIO`).
- **Domain (unit):** `FORMAT_MEDIA_TYPES` mapping; `build_sbom_annotations` output; unknown format
  rejected.
- **Use case (fakes):** new `FakeSbomGenerator` (journals `generate` calls). Assert *both* the copy
  branch and the rebuild branch call `generate` and `put_referrer` once per configured format with
  the placed digest; `BuildRequest.sbom` is gone. A generator failure fails that op (fail-hard) and
  reddens the report. `KNOCK_SBOM_FORMATS=["spdx-json","cyclonedx-json"]` ⇒ two referrers per image.
- **Acceptance gate — incident matrix, re-pointed (`tests/integration`, real syft, opt-in marker):**
  the Log4Shell-nested-JAR / openssl / liblzma / redis-present / runc-absent / bare-binary-mongod-absent
  matrix from ADR 0029, run against **standalone syft** (replacing the buildkit-syft-scanner build).
  Same assertions (capture + purls + runtime boundary + the documented bare-binary limit) — the
  permanent guard against silent depth regression.

## Docs to sync (same change as ship)

- **ADR:** new ADR (next free number) — "Unify SBOM generation on syft", **superseding the mechanism
  of ADR 0029** (mark 0029 superseded-in-part; its value/depth findings stand). Links to this spec.
- **C4 model** (`workspace.dsl` + `_export/` mermaid): now **does** change (ADR 0029's "C4 unchanged"
  no longer holds) — add `SbomGeneratorPort` + `SyftAdapter` to the Hexagon/Component views; the
  buildkit adapter loses the SBOM responsibility. syft is a bundled CLI tool driven by a subprocess
  adapter, like regctl / buildctl / cosign.
- **`docs/reference/`:** regen for `KNOCK_SBOM_FORMATS` (`make reference`).
- **`docs/examples/`:** update the SBOM example to show the referrer (both paths) and a CycloneDX
  config; no new `MirrorPolicy` field (format is `KNOCK_*` config, not policy).
- **Value-prop docs** (README, "Why knock?", `design.md`, roadmap): the honesty caveat *"rebuilt
  images; the ~1% copy path stays uncovered"* flips to **both paths covered**, and SPDX-only becomes
  SPDX + CycloneDX. A positive narrative update.
- **Dockerfile:** `+ syft`; the buildkit `attest:sbom` removal is code-only.
