# Keyless scan attestations so the Kyverno admission gate works (sigstore on kind)

**Status:** Design — approved 2026-06-25, pending implementation plan.

## Problem

The Kyverno admission gate (`verify-houba-scan`, component E4) cannot verify houba's scan
attestations, so it degrades to **deny-all**: it blocks the log4shell pod (beat 3b, the deny case
the demo probes) but would equally block a *validly attested* clean image. The demo never caught
this because beat 3b only tests the deny path.

Two distinct causes were found and the first was fixed:

1. **RBAC (fixed, commit `b33b01f`).** Kyverno's admission controller had no rights on the
   `houba/houba-attest-key` Secret, so the public key never loaded (`secrets … is forbidden` →
   `verifiedCount: 0`). An aggregate ClusterRole now grants a least-privilege `get` on that Secret.

2. **cosign-v3 ⇄ Kyverno key-mode incompatibility (this spec).** With the key loadable, Kyverno
   still fails. Root cause, established with evidence:
   - houba signs with **cosign v3.1.1** in **key mode**; attestations land as
     `application/vnd.dev.sigstore.bundle.v0.3+json` referrers (the new Sigstore bundle format).
   - `cosign verify-attestation --key cosign.pub --insecure-ignore-tlog` **succeeds** on the clean
     image → the attestation is valid and the kargo gate (`houba verify`) works.
   - Kyverno's **Cosign** verifier (does key mode) does not read the v0.3 bundle → "no matching
     attestations". Kyverno's **SigstoreBundle** verifier reads the v0.3 bundle but is
     **keyless-only** (built for GitHub Artifact Attestations); with a static key it returns "no
     matching signatures", even with `rekor.ignoreTlog: true`.
   - cosign v3.1.1 `attest` has **no flag** to emit the legacy format, so houba cannot side-step it
     on the signing side while staying on cosign v3.

This is an ecosystem gap (cosign-v3 key-mode bundles ⇄ Kyverno verifier), not a houba bug.

## Goal

Make the Kyverno gate genuinely enforce — admit a validly attested image and deny an unattested
one — by switching houba's scan attestations to **keyless** signing backed by an in-cluster
Sigstore (Fulcio + Rekor), which Kyverno's SigstoreBundle verifier supports. Because the
attestation is a single signed referrer read by **both** gates, the **kargo** gate (today working
in key mode) migrates to keyless verification in the same change.

Non-goal: removing key-mode from houba. Keyless is already a configured signer
(`HOUBA_ATTEST_SIGNER`); the demo flips the config. Key mode stays for adopters with a real KMS.

## Approach (chosen)

**Keyless on kind via [sigstore-scaffolding](https://github.com/sigstore/scaffolding)**, the
canonical in-cluster Sigstore for testing (Fulcio + Rekor + CTLog + Trillian + a TUF mirror).
Fulcio is configured to trust the **kube-API ServiceAccount OIDC issuer**, and cosign signs with
the workload's **projected ServiceAccount token** as the OIDC identity. This is the pattern
sigstore's own e2e uses; it needs no external IdP.

Rejected alternatives: a hand-rolled minimal Fulcio (off the beaten path, fragile OIDC config);
key mode (the status quo that does not work with Kyverno); accepting the limitation (leaves the
gate deny-all).

## Design by layer

Each layer is a unit with a clear contract; they communicate through the Sigstore trust root and
the signed bundle on the image.

1. **Sigstore stack (new prerequisite operator).** A pinned sigstore-scaffolding install (Makefile
   `sigstore` target + a `deploy/components/sigstore` reference, mirroring cert-manager/kargo/
   kyverno posture: demo prerequisite, never embedded; prod points at your/public Sigstore). It
   provides Fulcio/Rekor/CTLog and a TUF mirror, with Fulcio's OIDC config trusting the cluster's
   SA issuer (`kubectl get --raw /.well-known/openid-configuration` → issuer).

2. **houba signs keyless (config + small adapter change).** scan-attach (and the copy-path
   signer) set `HOUBA_ATTEST_SIGNER=keyless`, `HOUBA_ATTEST_FULCIO_URL` / `HOUBA_ATTEST_REKOR_URL`
   at the in-cluster services, and mount a projected SA token. `CosignAdapter.attest` keyless path
   already emits no `--key` and writes a signing-config; the likely addition is passing the SA
   token as the OIDC identity (`--identity-token`) and pointing cosign at the in-cluster trust
   root. The `houba-attest-key` Secret and `cosign-keygen` become unused in the demo (kept for the
   key-mode adoption path).

3. **kargo gate verifies keyless.** The scan-gate AnalysisTemplate flips from
   `HOUBA_ATTEST_SIGNER=key` to keyless verify: `HOUBA_ATTEST_VERIFY_IDENTITY` (the SA identity
   regexp) + `HOUBA_ATTEST_VERIFY_OIDC_ISSUER` (the SA issuer) + the trust root.
   `CosignAdapter.verify` keyless path already emits `--certificate-identity-regexp` /
   `--certificate-oidc-issuer`.

4. **Kyverno policy keyless.** `verify-houba-scan` uses `type: SigstoreBundle` with a `keyless`
   attestor (`issuer` = SA OIDC issuer, `subject`/`subjectRegExp` = the SA identity) and the
   in-cluster Fulcio/Rekor/CT roots; the `keys.publicKeys` block is dropped. The RBAC ClusterRole
   for the key Secret is removed (no longer read); any new read need (e.g. a trust-root ConfigMap)
   gets its own least-privilege grant.

5. **Trust-root distribution.** All three verifiers must trust the in-cluster Sigstore.
   Recommended: pull from scaffolding's **TUF mirror** (scaffolding-native, single source of
   truth) via `TUF_MIRROR`/`--trusted-root`. Fallback: bake the Fulcio/CT/Rekor roots into a
   ConfigMap each verifier mounts (no TUF client dependency, simpler but two copies to keep
   fresh). The plan picks one after a spike confirms cosign/Kyverno both consume it.

6. **Makefile / demo flow.** Install `sigstore` before any signing (new `demo` prerequisite,
   ordered after cert-manager, before scan-attach). Extend `demo-assert-gates` so beat 3b also
   asserts the **admit** case (a clean attested image is admitted), closing the blind spot that
   hid this whole class of bug.

7. **Docs / model sync (repo conventions).** Update the C4 model (`workspace.dsl` + `_export/`)
   for the new Sigstore actor/integration; add an ADR linking this spec; refresh
   `docs/examples/` and the kyverno/kargo component READMEs.

## Risks

- **Resource footprint.** Trillian + its DB + Fulcio + Rekor + CTLog + TUF is heavy on the
  single-node kind cluster — and a disk-exhaustion incident occurred during this work (the OSV
  mirror filled the node disk and wedged etcd). Check `df -h` before installing; size requests
  conservatively; document the added footprint.
- **OIDC SA-token flow.** Configuring Fulcio to trust the cluster SA issuer and getting cosign's
  `--identity-token` keyless flow working in an automated pod is the least-trodden part; spike it
  first.
- **Migrating the working kargo gate.** beat 3a passes today in key mode; the cutover must keep it
  green. Validate kargo keyless verify before flipping the policy.
- **All-or-nothing cutover.** One attestation, two readers — the signing change and both verifier
  changes must land together (or behind a single config flip) to avoid a window where one gate
  breaks.

## Testing (e2e on kind)

1. Sign a placed image keyless → `cosign verify-attestation` keyless (trust root) succeeds.
2. kargo: clean freight is admitted to prod (gate passes); log4shell freight is held (gate fails).
3. Kyverno: a clean attested demo image is **admitted**; log4shell is **denied** — the admit case
   now provable.
4. `make demo` green end-to-end on a fresh cluster, beats 3a/3b (incl. the new admit assertion)
   and 4 all passing.

## Phasing

- **P1** — Sigstore stack installs on kind; houba signs keyless; `cosign verify` (keyless, trust
  root) proves the attestation. No gate changes yet.
- **P2** — kargo gate verifies keyless; beat 3a stays green.
- **P3** — Kyverno policy keyless; beat 3b asserts both deny and admit; drop the key-mode RBAC.
- **P4** — docs/C4/ADR/examples sync; adoption notes (prod Sigstore).

Each phase is independently verifiable on kind before the next.
