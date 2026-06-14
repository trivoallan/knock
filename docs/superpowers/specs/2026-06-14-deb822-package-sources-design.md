# Design — deb822 support in `rewritePackageSources`

- **Date:** 2026-06-14
- **Status:** approved (design), pending implementation plan
- **Scope:** extend the `rewritePackageSources` transform step to also host-swap deb822
  `/etc/apt/sources.list.d/*.sources` files. Pure domain (one Dockerfile fragment line) + tests +
  docs. No new ports/adapters, no config change, no C4 change.

## Problem

`rewritePackageSources` (`houba/domain/transforms/steps.py`) rewrites an image's package sources to
an internal mirror during the hardening rebuild. Its apt branch currently host-swaps:

- `/etc/apt/sources.list` (one-line apt)
- `/etc/apt/sources.list.d/*.list` (one-line apt)
- `/etc/apk/repositories` (apk)

It does **not** touch the **deb822** format `/etc/apt/sources.list.d/*.sources`, which is the
**default** on Debian 12 (`debian.sources`) and Ubuntu 24.04+ (`ubuntu.sources`). On those bases the
hardening rebuild leaves package sources pointing upstream — the mirror swap silently no-ops, which
defeats the step's purpose (and was flagged as a known deferral in the transform-hardening spec).

## Decision

Add a third apt rewrite targeting `/etc/apt/sources.list.d/*.sources`, using the **same** host-swap
`sed` as the existing `.list` rewrites. In deb822 the host lives in the `URIs:` field as a plain
`scheme://host/path` URL, so `sed -ri 's#https?://[^/]+#{mirror}#g'` applies unchanged; `Signed-By:`
(a filesystem path, not an `http(s)` URL) is left untouched. No deb822 *parsing* — the line-oriented
sed is sufficient and keeps the step pure and dependency-free (YAGNI).

- **apt only.** deb822 is an apt format; the apk branch is unchanged.
- **No `transform_version` change.** `transform_version` hashes only the *declared* inputs (step
  name/params + resolved resource data), not houba's codegen. Adding the `.sources` rewrite changes
  the emitted fragment but not the hash, so already-hardened deb822 images do **not** mass-rebuild;
  they pick up the fix on their next natural rebuild (source digest moves, or the transform changes).
  This keeps the clean invariant `transform_version = f(declared transform)`. Documented behaviour.

## Implementation

In `RewritePackageSources.fragment`, inside `if m.apt:`, after the existing `*.list` rewrite, append:

```python
rewrites.append(
    f"if ls /etc/apt/sources.list.d/*.sources >/dev/null 2>&1; then "
    f"sed -ri 's#https?://[^/]+#{m.apt}#g' /etc/apt/sources.list.d/*.sources; fi"
)
```

The guard (`if ls … >/dev/null 2>&1`) mirrors the existing `*.list` rewrite, so images without any
`.sources` file are unaffected. Everything else (the `RUN set -eux; …` joining, the apk branch, the
empty-rewrites short-circuit) is unchanged.

## Files

- **Modify** `houba/domain/transforms/steps.py` — the one rewrite line above.
- **Modify** `tests/unit/domain/transforms/test_steps.py` — assert the `.sources` rewrite is emitted
  in the apt fragment (and that the apt-only / apk cases still hold).
- **Docs** — `docs/architecture/design.md` (the living status doc): remove deb822 from the "Deferred"
  list. The two 2026-06-11 specs that recorded deb822 as deferred
  (`…-image-transform-hardening-design.md`, `…-transform-steps-pluggables-design.md`) are
  point-in-time records — don't rewrite them; add a one-line "(addressed 2026-06-14 — see deb822
  spec)" pointer to each. (`docs/examples/README.md` does not mention deb822 — no change there.)

## Testing

Pure-domain unit tests (TDD):

1. `test_rewrite_fragment_apt_*` — the apt fragment's `RUN` line now contains
   `/etc/apt/sources.list.d/*.sources` alongside `/etc/apt/sources.list` and
   `/etc/apt/sources.list.d/*.list`; apk still present/absent per the mirror fields.
2. A focused assertion that the deb822 rewrite uses the same host-swap sed (so a deb822 `URIs:` line
   is covered by the same regex).

No `transform_version` test change (hashed inputs are unchanged — existing version tests stay green).
Gates: `uv run pytest` (≥ 80 % global, ≥ 90 % `houba.domain`), `ruff`, `mypy houba`.

## Out of scope

- deb822 *parsing* / field-aware rewriting (the sed covers it).
- Forcing a re-hash / mass rebuild of existing hardened images (rejected — clean version invariant).
- apk / non-apt formats. CycloneDX-style structured sources. New mirror config fields.

## Architecture / C4

None. Internal codegen of an existing transform step — no actor, external system, port, adapter, or
error change. No `workspace.dsl` edit and no ADR (not architecture-shifting).
