# Design — `CosignAdapter` migration to cosign v3 signing-config

**Status:** approved (brainstorm), pending implementation plan.
**Date:** 2026-06-14.
**Area:** `adapters` (CosignAdapter), `domain` (attestation), `tests`.

## Problem

houba bundles **cosign v3.1.1** (Dockerfile, since #51). The `CosignAdapter`
(`houba/adapters/cosign_cli.py`) was written against cosign v2 flags and is **broken with the
bundled binary** — i.e. the signing feature shipped in 0.4.0 does not work with its own cosign.

Verified empirically against real cosign v3.1.1 (key signer, throwaway `registry:2`):

| Invocation (current `_signing_args`) | Result on v3.1.1 |
|---|---|
| `--tlog-upload=false` (air-gapped key/kms) | **exit 1** — `--tlog-upload=false is not supported with --signing-config or --use-signing-config` |
| `--rekor-url <url>` (tlog enabled) | **exit 1** — `cannot specify service URLs and use signing config` |
| `--fulcio-url <url>` (keyless) | same family — service URL rejected (not run in isolation; keyless needs OIDC) |
| `--key <k> --signing-config <cfg>` | **exit 0** — signs, no service-URL flags |

Root cause: **cosign v3 enables the signing-config by default**, so the v2 service-URL / tlog flags
(`--fulcio-url`, `--rekor-url`, `--tlog-upload`) are rejected at runtime. Fulcio/Rekor must be
expressed via a `--signing-config` file.

**Blast radius:** two call sites now sign through this one adapter — `use_cases/reconcile.py`
(rebuild-path transform attestation) and `use_cases/attach.py` (scan-referrer attestation, added in
#56). Both are non-functional on v3. Fixing the single `CosignAdapter.attest` impl fixes both.

**Good news (verified, no change needed):** storage stays referrer-compatible. cosign v3 writes the
attestation to the **OCI referrers fallback tag** `sha256-<digest>` (an OCI image index whose entries
carry `artifactType: application/vnd.dev.sigstore.bundle.v0.3+json` and a `subject`), because
`registry:2` does not implement the `/referrers/` API. `regctl` (houba's reader) resolves the
fallback tag transparently, so **`audit` / `purge` / `attach` referrer reads are unaffected**.

## Decisions (from brainstorm)

1. **Scope:** support **key / kms** fully (± optional Rekor), tested. **keyless is best-effort** —
   `caUrls` is emitted, but keyless also needs an OIDC identity token houba does not supply, so it is
   documented as unverified against v3 (not a tested path).
2. **Construction:** a **pure domain function** builds the signing-config dict; the adapter writes it
   to a tempfile and passes `--signing-config`. (Not shelling out to `cosign signing-config create` —
   keeps the logic pure, unit-testable, and the adapter thin.)
3. **Real-cosign test:** an opt-in integration test, **skipped unless a real `cosign` is on PATH**.
   A dedicated always-on CI job is noted as a future follow-up, not built here.

## Design

### 1. Pure builder — `domain/attestation.py`

Add a dependency-free function (no clock, no I/O) that reproduces the captured signing-config **v0.2**
JSON schema:

```python
SIGNING_CONFIG_MEDIA_TYPE = "application/vnd.dev.sigstore.signingconfig.v0.2+json"
_EPOCH = "1970-01-01T00:00:00Z"  # validFor.start = "valid from the beginning" (no clock needed)

def build_signing_config(*, fulcio_url: str, rekor_url: str, operator: str) -> dict:
    cfg: dict = {"mediaType": SIGNING_CONFIG_MEDIA_TYPE, "rekorTlogConfig": {}, "tsaConfig": {}}
    if fulcio_url:
        cfg["caUrls"] = [_service(fulcio_url, operator)]
    if rekor_url:
        cfg["rekorTlogUrls"] = [_service(rekor_url, operator)]
        cfg["rekorTlogConfig"] = {"selector": "ANY"}
    return cfg

def _service(url: str, operator: str) -> dict:
    return {"url": url, "majorApiVersion": 1, "validFor": {"start": _EPOCH}, "operator": operator}
```

Captured shapes this reproduces (from real `cosign signing-config create` v3.1.1):

- **empty / air-gapped** — `{"mediaType": …, "rekorTlogConfig": {}, "tsaConfig": {}}` *(verified exit 0)*
- **rekor** — adds `rekorTlogUrls:[{url, majorApiVersion:1, validFor:{start}, operator}]` + `rekorTlogConfig:{selector:"ANY"}`
- **fulcio (keyless)** — adds `caUrls:[{…same shape…}]`

`operator` = `builder_id` if set, else the constant `"houba"`. `_EPOCH` is a constant so the function
stays pure (no clock dependency).

### 2. `CosignAdapter.attest` rewrite

- **Drop** `_signing_args`' service-URL / tlog flags (`--fulcio-url`, `--rekor-url`,
  `--tlog-upload`).
- **Keep** `--key <key_ref>` for `kms` / `key` signers (a key reference is *not* a service URL).
- Build the signing-config dict via `build_signing_config(fulcio_url=cfg.fulcio_url,
  rekor_url=cfg.rekor_url, operator=cfg.builder_id or "houba")`, write it as `signing-config.json`
  into the existing `TemporaryDirectory` (alongside `predicate.json`), and pass
  `--signing-config <path>`.

New argv:

```
attest --yes --type <T> --predicate <pred.json> [--key <K>] --signing-config <cfg.json> <subject_ref>
```

Everything else (predicate tempfile, `--yes`, digest scrape from stderr/stdout, `CosignError` on
non-zero exit, 300s timeout, lazy binary resolution) is unchanged.

`AttestSettings` (config.py) is **unchanged** — the same `HOUBA_ATTEST_*` fields drive the new
construction; `builder_id` is reused as the signing-config `operator`.

### 3. Tests (TDD)

- **Unit (pure)** — `tests/unit/domain/test_attestation.py` (or a new module): `build_signing_config`
  for the three shapes (empty, rekor-only, fulcio+rekor), asserting the exact dict, including
  `operator` fallback to `"houba"` and `builder_id` override.
- **Integration (fake-bin)** — update `tests/fake-bins/cosign` to accept `--signing-config` / `--key`
  and log argv; `tests/integration/test_cosign_cli.py` asserts the new argv for key/kms (air-gapped)
  and the rekor case, and asserts the **forbidden** flags (`--fulcio-url`, `--rekor-url`,
  `--tlog-upload`) are **absent**.
- **Existing** — `test_reconcile_attestation.py`, `test_attach.py`, `test_di_attestor.py`, fakes
  tests stay green (they exercise the port via the fake attestor, not cosign flags).
- **Opt-in real-cosign** — a new integration test guarded by
  `@pytest.mark.skipif(shutil.which("cosign") is None)` that runs `cosign attest` end-to-end against a
  throwaway `registry:2` (key signer, empty signing-config) and asserts a referrer lands on the
  subject (read back via `regctl`). Mirrors today's manual verification; skipped on dev machines
  without cosign. A dedicated CI job that installs cosign is a future follow-up.

## Out of scope / non-goals

- Re-pinning cosign to v2.x (rejected in brainstorm — forward path chosen).
- Migrating *verification* (`verify-attestation`) — houba only signs.
- A guaranteed keyless flow (best-effort only; needs ambient OIDC).
- TSA (timestamp authority) support — `tsaConfig` stays empty.

## Architecture / C4 impact

**None.** The hexagon is unchanged: `AttestorPort → CosignAdapter → signing service`. No new port,
adapter, external system, or error type. Therefore no `workspace.dsl` change and no ADR (the
spec→ADR mirror is for architecture-shifting specs). Documentation touch: a one-line note in the
`design.md` provenance section that attestation uses a cosign **signing-config** (v3).

## Verification (acceptance)

- `uv run pytest` green; coverage gates hold (≥ 80 % global, ≥ 90 % on `houba.domain`).
- `uv run ruff check . && uv run ruff format --check . && uv run mypy houba` clean.
- Manual (already done once, to be re-runnable via the opt-in test): real cosign v3.1.1
  `attest --key … --signing-config <empty> <ref>` → exit 0, referrer readable via `regctl`.
