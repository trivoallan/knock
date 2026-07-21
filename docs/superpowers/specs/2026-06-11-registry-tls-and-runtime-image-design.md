# Registry TLS/auth + runtime-image regctl — design

> **Status:** approved design, pre-implementation. Makes the reconcile + rebuild path
> (Phase 6, PR #24) actually runnable: the shipped image can run `regctl`, and knock can
> reach internal-CA / HTTP registries without manual setup. Terminal step: `writing-plans`.
>
> **Branch note:** stacked on `feat/image-transform-hardening` (Phase 6). Rebase onto `main`
> once PR #24 merges.

## 1. Context & motivation

knock's whole runtime uses **`regctl`** as its registry client (list/inspect/copy/annotate/
delete/login). Two gaps block real-world operation:

1. **The runtime image ships only `buildctl`** (`Dockerfile` copies it from `moby/buildkit`)
   — **`regctl` is absent**, so the published image cannot run `knock reconcile` at all.
   This is a shipping bug, not a feature gap.
2. **No per-registry TLS/CA configuration.** `--tls disabled` is set only inside `login`, so
   an **anonymous HTTP** registry (no creds → no login) is never told it's HTTP and the first
   `tag ls` fails over HTTPS — today's manual workaround is `regctl registry set <host>
   --tls disabled`. And a registry fronted by an **internal CA** has no way to be trusted.

This work closes both so the hardening/copy path runs end-to-end against a real org registry.

## 2. Scope

**In:**
- Bundle `regctl` in the runtime image alongside `buildctl`.
- `RegistryConfig.ca_cert` (path to a CA PEM that knock should trust for that registry).
- A `configure_registry(host, *, tls_verify, ca_cert)` port method that applies the per-registry
  TLS mode + CA via `regctl registry set`, called once per host before any operation.
- Remove the now-obsolete manual `regctl registry set --tls disabled` workaround from the docs.

**Out (deferred, YAGNI):** bearer / identity-token auth (username+password already covers
Harbor/GHCR robot tokens); mTLS client certs; inline-PEM registry CA (path only — k8s mounts
the CA as a file, same as the transform CA roster). Per-registry CA stays **separate** from the
transform CA roster (`KNOCK_TRANSFORM_CA_CERTS`): registry trust ≠ image hardening — the roadmap
keeps those concerns distinct.

## 3. Runtime image — bundle regctl

`Dockerfile` runtime stage copies the static `regctl` binary from the official
`regclient/regctl:<pinned>` image, mirroring how `buildctl` is copied from `moby/buildkit`:

```dockerfile
COPY --from=regclient/regctl:<pinned-version> /usr/local/bin/regctl /usr/bin/regctl
```

(The implementer pins a current `regclient/regctl` release and verifies the binary path inside
that image — it is a distroless image with the static binary; confirm the exact source path.)
Update the stale `# Phase B — Python CLI + buildctl` header. **Smoke test:** `docker build`
then `docker run --entrypoint sh knock:dev -c "regctl version && buildctl --version"` and
`docker run knock:dev reconcile --help`. No Python code changes.

## 4. Per-registry TLS/CA

### 4.1 Config
Add to `RegistryConfig` (in `config.py`), alongside `host`/`username`/`password`/`tls_verify`:

```python
    ca_cert: str | None = None  # path to a CA PEM regctl should trust for this registry's TLS
```

`tls_verify` (already present) keeps its meaning: `False` ⇒ plain HTTP / skip-verify. Auth stays
`username`/`password` (robot tokens ride in `password`). No new env contract beyond the new key
inside the existing `KNOCK_REGISTRIES` JSON.

### 4.2 Port + adapter
New method on `RegistryPort` (and its fake + the regctl adapter):

```python
def configure_registry(self, host: str, *, tls_verify: bool, ca_cert: str | None) -> None: ...
```

`RegctlAdapter.configure_registry` runs:
```
regctl registry set <host> --tls <enabled|disabled> [--cacert <ca_cert>]
```
- `--tls disabled` when `not tls_verify`, else `--tls enabled` (explicit, so regctl never guesses).
- `--cacert <path>` only when `ca_cert` is set.
`regctl registry set` persists this in regctl's config for the rest of the run, so every later
`tag ls`/`copy`/etc. against that host honors it. `FakeRegistryPort` journals the calls
(e.g. `self.configured: list[tuple[str, bool, str | None]]`). A new `tests/fake-bins/regctl`
branch handles `registry set` (no-op + argv logged) so the integration test can assert the flags.

### 4.3 Use-case wiring
In `reconcile_policies` (`use_cases/reconcile.py`), the apply phase already logs in **once per
host** (`logged_in: set[str]`). Add a sibling **configure-once-per-host** step that runs
`registry.configure_registry(cfg.host, tls_verify=cfg.tls_verify, ca_cert=cfg.ca_cert)` the first
time a host is seen, **before** login and before any list/inspect/copy. (Configure owns TLS+CA;
login owns credentials.) Run it for every used host — for a default HTTPS + public-CA registry it
simply re-asserts `--tls enabled` with no CA, which is harmless and keeps behavior explicit.

The existing `login`'s `--tls disabled` argument may stay (redundant once the registry is
configured) or be dropped — the implementer picks the cleaner of the two; behavior is unchanged
either way because `configure_registry` now authoritatively sets the TLS mode first.

### 4.4 Docs
- `README.md` registry-config table: add the `ca_cert` key.
- Remove the manual `regctl registry set localhost:5001 --tls disabled` workaround from
  `docs/examples/README.md` (it is now automatic from `tls_verify: false` in the roster) and,
  if present, note that a local HTTP registry just needs `tls_verify: false` in `KNOCK_REGISTRIES`.

## 5. Architecture & units

| Unit | Change | Layer |
| --- | --- | --- |
| `Dockerfile` | copy `regctl` from `regclient/regctl`; refresh comment | image |
| `config.py` `RegistryConfig` | add `ca_cert: str \| None` | config |
| `ports/registry.py` `RegistryPort` | add `configure_registry(...)` to the Protocol | ports |
| `adapters/regctl_cli.py` | implement `configure_registry` (`regctl registry set`) | adapter |
| `tests/fakes/registry.py` `FakeRegistryPort` | journal `configure_registry` calls | test infra |
| `tests/fake-bins/regctl` | handle `registry set` (log argv) | test infra |
| `use_cases/reconcile.py` | configure-once-per-host before login/ops | use case |
| `cli/_di.py` | no change (RegctlAdapter already wired) | — |
| `README.md`, `docs/examples/README.md` | `ca_cert` row; drop the TLS workaround | docs |

Hexagonal rule holds: the new I/O (`regctl registry set`) lives only in the adapter; the use case
orchestrates through the port; `config.py` stays the sole env reader. No C4-model change — this
adds no actor/external-system/integration (it hardens the *existing* knock→registry edge).

## 6. Testing

- **Config:** `RegistryConfig` parses `ca_cert` from a `KNOCK_REGISTRIES` entry; absent ⇒ `None`.
- **Adapter (fake-bin):** `configure_registry` emits `registry set <host> --tls disabled` when
  `tls_verify=False`; `--tls enabled` otherwise; appends `--cacert <path>` only when set.
- **Use case (fakes):** `configure_registry` is called once per unique host, before the first
  `list_tags`/`copy`, with the host's `tls_verify`/`ca_cert`; a second plan on the same host does
  not reconfigure. Existing reconcile tests stay green (add `configured` to the fake; default
  behavior unchanged).
- **Image:** a CI/manual smoke step asserting `regctl` is on `PATH` in `knock:dev`.
- Coverage gates unchanged (≥ 80 % global, ≥ 90 % `knock.domain` — this work is config/adapter/
  use-case, not domain, so the domain gate is unaffected).
