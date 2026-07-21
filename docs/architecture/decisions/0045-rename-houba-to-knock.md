# 45. The tool is renamed houba → knock; the front door gets a name that means it

Date: 2026-06-26

## Status

Accepted — implements the [rename spec](../../superpowers/specs/2026-07-05-rename-houba-to-knock-design.md).

## Context

"houba" (a Marsupilami onomatopoeia) is arbitrary with respect to the product. The thesis is that
the tool is the **single front door** for external images — every image is rebuilt, hardened, and
stamped as it passes one controlled entry point. **knock** carries that: you knock at a door, and
`knock scan` / `attach` / `verify` read as the imperative of approaching it. It also retires the
"NOK = not OK" / Norwegian-Krone collisions the interim "nok" carried — actively misleading for a
tool that emits pass/fail gates. A second register reinforces it: Jules Romains' *Knock ou le
Triomphe de la médecine* (1923) — *« tout homme bien portant est un malade qui s'ignore »* — is
the coverage thesis exactly: no image is presumed clean until screened and stamped at the front
door.

## Decision

- **Name = `knock`.** CLI command `knock`, import package `knock/`. Bare `knock` and `nok` are both
  taken on PyPI, so the **distribution name is `knock-oci`** (`pip install knock-oci`, command still
  `knock`; the runtime version lookup is `importlib.metadata.version("knock-oci")`) — only the
  distribution name lives in a global namespace. This refines the rename spec, which assumed a bare
  `knock` distribution.
- **Repo** `trivoallan/houba` → `trivoallan/knock` (GitHub redirects the old path).
- **External contracts flipped now — hard cutover, no aliases.** `env_prefix="HOUBA_"` →
  `"KNOCK_"` and the default label prefix `io.houba` → `io.knock`, in this same change. Nothing is
  deferred. A dual-read back-compat shim was considered and **rejected** (pre-1.0; a shim would
  itself be a deferral). Operators take a one-time migration: re-key `HOUBA_*` env to `KNOCK_*`,
  and add an `io.knock.*` arm to any label-keyed admission/policy. Images placed before the cutover
  keep `io.houba.*` (knock never rewrites placed manifests); images placed after carry `io.knock.*`.
- **Frozen provenance identifiers move with the rename.** The predicate URIs
  (`https://knock.dev/predicate/{transform,scan}/v1`) and artifact types
  (`application/vnd.knock.*`) are renamed on the write side. Per the spec's premise 5, these are
  stamped on **already-signed** attestations/referrers; verification of the pre-rename cohort
  (`houba.dev` / `vnd.houba.*`) requires the verifier to accept **both** old and new until that
  cohort ages out. **This dual-accept read path is NOT yet implemented** — see Consequences.
- **Historical ADRs/specs rewritten** to "knock" for consistency (filenames too); the glossary
  records the former name.

## Consequences

- A **clean end-to-end rename** — no naming mismatch survives on the write side. The config
  breakage is intentional and bounded to the two contract *values*, documented for operators.
- **Open follow-up (read-side compat):** with the predicate URIs / artifact types renamed but no
  dual-accept in `verify`, verification of attestations signed **before** the rename (bearing
  `houba.dev` / `vnd.houba.*`) will not match. If any signed cohort exists in a registry, `verify`
  must be taught to accept both identifier families until it ages out. Tracked as the sole
  non-mechanical loose end of this rename.
- **Zero domain logic and zero schema-shape change** — internal symbols (`RegctlAdapter`, …) never
  carried the brand, so the change is import-path + prose churn (plus the contract values) under
  the existing test/type/coverage gates (global ≥80 %, `knock.domain` ≥90 %), which stay green.
- The C4 model's central software system is renamed (no actor/system/integration added or removed);
  `workspace.dsl` + `_export/*.mmd` + `README.md` are updated in the same change.
