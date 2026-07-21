# 25. `attach` registry-config parity via shared `ensure_registry_session` helper

Date: 2026-06-16

## Status

Accepted.

## Context

`knock attach` was the one command in the fleet whose registry access was not governed by the
declared `KNOCK_REGISTRIES` roster: it called `registry.inspect` / `put_referrer` straight on
the `<ref>` and relied on whatever ambient regctl/docker config the pod happened to carry.
`reconcile`, `audit`, and `purge` all call a `configure_registry` + `login` block before
touching a registry; `attach` did not, making it inconsistent.

## Decision

`attach` now authenticates via the `KNOCK_REGISTRIES` roster: by default it matches the image
ref's host against `cfg.host` in the roster; `--registry <name>` forces a specific roster entry
(consistent with `audit` / `purge`); when no roster entry matches and no `--registry` is given,
it silently falls back to ambient regctl config, preserving the previous behaviour. The
`configure_registry` + `login` block is extracted into a new shared use-case helper
`ensure_registry_session` (in `knock/use_cases/registry_session.py`), idempotent via a
caller-owned `logged_in: set[str]` keyed on host; `reconcile` and `audit` are refactored to
call it instead of duplicating the block.

## Consequences

- All four verbs (`reconcile`, `audit`, `purge`, `attach`) reach registries through a single,
  consistently governed code path.
- `--registry <name>` with an unknown name raises `ConfigError` (exit 3), consistent with the
  rest of the CLI.
- No change to the `KNOCK_REGISTRIES` schema or any port/adapter; the parity is purely at the
  use-case layer.

Full design spec:
[2026-06-16-attach-registry-config-parity-design.md](../../superpowers/specs/2026-06-16-attach-registry-config-parity-design.md)
