# Changelog

## [0.3.0](https://github.com/trivoallan/houba/compare/v0.2.0...v0.3.0) (2026-06-12)


### Features

* **deploy:** reference deployment — kustomize, kind demo, blast-radius consumer ([#29](https://github.com/trivoallan/houba/issues/29)) ([68d7535](https://github.com/trivoallan/houba/commit/68d75352c9335807a5267a10f7284d733fbf7a17))
* **domain:** pluggable transform-step registry (+ setTimezone, discriminated-union schema) ([#26](https://github.com/trivoallan/houba/issues/26)) ([3aad9dd](https://github.com/trivoallan/houba/commit/3aad9dddb0bf198163feb39dbc280b658c4b12f9))
* image transform / hardening — the rebuild path (Phase 6) ([#24](https://github.com/trivoallan/houba/issues/24)) ([79e9dfa](https://github.com/trivoallan/houba/commit/79e9dfaba51a91e30f58af05848637b81bf54c44))
* make the reconcile path runnable — bundle regctl + per-registry TLS/CA ([#27](https://github.com/trivoallan/houba/issues/27)) ([de46501](https://github.com/trivoallan/houba/commit/de465015ddc6369d48238fcd0d322544dcfee424))
* **reconcile:** structured two-stream output + per-policy resilience ([#25](https://github.com/trivoallan/houba/issues/25)) ([1aa22f2](https://github.com/trivoallan/houba/commit/1aa22f24ca9a18a56ae2ca3c0602781faf327a3d))


### Bug Fixes

* **image:** run runtime image as non-root (uid 65532) ([#30](https://github.com/trivoallan/houba/issues/30)) ([409b0fe](https://github.com/trivoallan/houba/commit/409b0febf5d08c29a496190e518df6a6bd54880a))


### Documentation

* **architecture:** VS Code launch config for Structurizr C4 viewer ([#22](https://github.com/trivoallan/houba/issues/22)) ([53e2ad3](https://github.com/trivoallan/houba/commit/53e2ad362b2dbf0c7b5e97aa245561a91e0ad1af))
* **specs:** SLSA / in-toto attestation design — the heavy-provenance layer ([#28](https://github.com/trivoallan/houba/issues/28)) ([5f36c15](https://github.com/trivoallan/houba/commit/5f36c151d2bf0ee5e51952f1728410ff9ca59483))

## 0.2.0

Initial public release.

`houba reconcile <dir>` — declarative **MirrorPolicy** reconciliation for external OCI
artifacts: regex/semver/name tag selection, derived moving-tag aliases, per-variant
expansion, provenance-based change detection, and OCI provenance stamping applied over
`regctl` (copy path). Multi-registry env-roster config; structured run summary.
