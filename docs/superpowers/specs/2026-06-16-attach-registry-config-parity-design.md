# `attach` registry-config parity — design

*Status: design. Roadmap item: **Now → "`attach` registry-config parity"**. Date: 2026-06-16.*

## Why

houba's roster of real registries — host, credentials, TLS verification, per-registry CA — is declared
once in `HOUBA_REGISTRIES` and consumed by `reconcile`, `audit`, and `purge`. Each of those, before
touching a registry, calls the same two-line block: configure the registry's TLS/CA, then log in if
credentials are present.

`houba attach` does **not**. It calls `registry.inspect` / `put_referrer` / (optionally) `attest`
straight on the `<ref>` and relies on whatever ambient regctl/docker config the pod happens to carry.
That is the one command in the fleet whose registry access is *not* governed by the declared roster —
an inconsistency the roadmap calls out: *"Wire the `HOUBA_REGISTRIES` roster into `attach` as in
`reconcile`, instead of relying on ambient regctl config."*

This is **parity**, not a new capability: `attach` should reach a registry exactly the way the other
verbs do.

## The structural difference to bridge

In `reconcile`, the registry resolves from the **logical name** a policy's destination carries
(`resolve_registry(dest.registry, roster)`). In `attach` there is no policy — only an arbitrary
`<ref>` such as `harbor.corp.example.com/team/app:1.2.3`. So `attach` must select the roster entry a
different way: **by matching the ref's host against `cfg.host`.**

## The decision

- **Selection: host-match by default, `--registry <name>` as override.**
  - No flag → parse the host from `<ref>` and find the roster entry whose `cfg.host` equals it.
    "Just works" — the host is already in the ref, so parity with `reconcile` needs no extra input.
  - `--registry <name>` → resolve that roster entry explicitly via the existing `resolve_registry`,
    **even if the ref's host differs** (documented escape hatch: pull-through proxy, a ref with no
    explicit host, or any host/roster-name mismatch). Consistent with `audit` / `purge`, which already
    expose `--registry`.

- **No match → silent fallback to ambient config (today's behaviour).** When no `--registry` is given
  and the ref's host is in no roster entry (including a ref with no host token → docker.io implied, and
  an empty roster), `attach` configures nothing and lets regctl use its existing config. Rationale:
  `attach` targets images that often live in public or already-reachable registries, and the roster
  holds houba's **destination** registries, not necessarily every registry it might stamp. `attach`
  does not rewrite the image — it attaches a referrer — so the "always wired" guarantee buys little
  here and forcing roster membership would add friction for no benefit.

- **`--registry <name>` with an unknown name → `ConfigError` (exit 3).** Falls out of reusing
  `resolve_registry`, which already raises on an unknown name. Consistent with the rest of the CLI.

## Components (purest → most I/O)

**1. `domain/scan/refs.py` — `registry_host(ref) -> str | None` (pure)**

Extracts the leading host component of an OCI ref *when it is host-like* (the first path segment
contains `.` or `:`, or equals `localhost`); otherwise `None`. A bare `app:1.2.3` (docker.io implied)
yields `None`. Shares the same host-with-port caution as the neighbouring `pin_to_digest` (the colon
before the last `/` is part of the host, not a tag separator).

**2. `config.py` — `match_registry_by_host(ref, roster) -> tuple[str, RegistryConfig] | None` (pure)**

Sits beside `resolve_registry`. Calls `registry_host`, then returns the `(name, cfg)` whose
`cfg.host` equals that host, else `None`. Never raises — `None` is the fallback signal. Reading
config models, not `os.environ`, so it belongs with the other roster resolvers.

**3. `use_cases/registry_session.py` — `ensure_registry_session(registry, cfg, logged_in)` (new, shared)**

The `configure_registry` + conditional `login` block, idempotent via a caller-owned `logged_in: set[str]`
keyed on `cfg.host`. **`reconcile.py` and `audit.py` are refactored to call it** — extracting the
duplicated block *is* the parity. Behaviour is byte-for-byte what those two do today, so their
existing tests stay green.

**4. `use_cases/attach.py` — `attach_scan(...)` gains `roster` + `registry_override`**

Signature additions: `roster: dict[str, RegistryConfig] = {}`, `registry_override: str | None = None`.
Before `registry.inspect(image_ref)`:

- if `registry_override` is set → `resolve_registry(registry_override, roster)` (raises `ConfigError`
  on an unknown name);
- else → `match_registry_by_host(image_ref, roster)`;
- if that yields a `cfg` → `ensure_registry_session(registry, cfg, logged_in=set())`; if `None` → no-op.

The session setup lives **inside** `attach_scan` (as it does inside `reconcile`/`audit`), not in the
CLI layer.

**5. `cli/attach.py`**

Adds `--registry <name>` (help: "Roster entry to authenticate against (overrides host-matching).").
Passes `roster=container.settings.registries` and `registry_override=<flag>` into `attach_scan`.

## Error handling

| Situation | Outcome |
|-----------|---------|
| `--registry X`, `X` unknown | `ConfigError` → exit 3 |
| no `--registry`, ref host not in roster | no-op fallback (ambient config; exit unchanged) |
| `--registry X`, host of ref differs from `X.host` | override wins — session for `X` |
| empty roster, no `--registry` | no-op fallback |

## Testing (TDD, one behaviour per commit)

- **domain** (`test_refs.py`): `registry_host` — host:port, host with a dot, bare name → `None`,
  `localhost`, digest-pinned ref.
- **config** (`test_config.py` / resolver tests): `match_registry_by_host` — match, no-match, no-host.
- **use_case** (`test_registry_session.py`): `ensure_registry_session` — configures + logs in once,
  idempotent on the same host via `logged_in`, skips `login` when the cfg has no credentials
  (asserted through `FakeRegistryPort` journals).
- **use_case** (`test_attach.py`): session triggered on a host match; no-op when no match (no
  `configure_registry`/`login` journalled); `--registry` override path; `ConfigError` on an unknown
  `--registry`.
- **non-regression**: existing `reconcile` / `audit` tests stay green after the extraction.

Coverage gates unchanged: the new pure helpers (`registry_host`, `match_registry_by_host`) land under
the ≥ 90 % `houba.domain` / config resolver expectations; the use-case helper under the ≥ 80 % global
gate.

## Docs / architecture sync (same change)

- **ADR** under `docs/architecture/decisions/` mirroring this spec (thin, links here).
- **C4 Component view** in `docs/architecture/workspace.dsl`: the new `registry_session` use-case helper
  shared by `reconcile` / `audit` / `attach`; refresh the committed Mermaid export under
  `docs/architecture/_export/`.
- **`docs/examples/`**: extend the `attach` walkthrough with the `--registry` flag and the roster
  wiring (host-match by default, override when needed).

## Out of scope

- Generalizing `attach` beyond CVE (the `regis` / Trivy-native / CycloneDX mappers) — separate Now item.
- The signed-coverage audit tier — separate Now item.
- Any change to how the roster itself is declared (`HOUBA_REGISTRIES` schema is untouched).
