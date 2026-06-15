# Changelog

## [0.6.0](https://github.com/trivoallan/houba/compare/v0.5.0...v0.6.0) (2026-06-15)


### Features

* complete attestation coverage — sign copy path + idempotent skip-backfill ([#77](https://github.com/trivoallan/houba/issues/77)) ([9a3515a](https://github.com/trivoallan/houba/commit/9a3515aaf0ac645577d85af95cfbf53d7b874144))
* **deploy:** ArgoCD App-of-Apps reference deployment (variant) ([#79](https://github.com/trivoallan/houba/issues/79)) ([98f2669](https://github.com/trivoallan/houba/commit/98f26698b8498c5f6f3a745dbf98c3bcb5ea7257))
* freeze org.opencontainers.image.revision semantics ([#80](https://github.com/trivoallan/houba/issues/80)) ([dad2ffc](https://github.com/trivoallan/houba/commit/dad2ffc22642fa1500f779aee9eafa70ec9ff0f3))


### Documentation

* **roadmap:** mark single-front-door mandate validated ([#76](https://github.com/trivoallan/houba/issues/76)) ([5d27d17](https://github.com/trivoallan/houba/commit/5d27d17254d942a92f2699e466856baeffc50c70))
* **roadmap:** restructure to Now/Next/Later ([#74](https://github.com/trivoallan/houba/issues/74)) ([bb7c172](https://github.com/trivoallan/houba/commit/bb7c172a5338c6d3e89c118bd46a2cb8ee4f5a23))

## [0.5.0](https://github.com/trivoallan/houba/compare/v0.4.0...v0.5.0) (2026-06-15)


### Features

* **deploy:** buildkitd autoscaling — KEDA scale-up 1→K (impl of ADR 0016) ([#59](https://github.com/trivoallan/houba/issues/59)) ([baaca35](https://github.com/trivoallan/houba/commit/baaca354ee6d573be9caca0ef3c56f5c3e53aa0e))
* **domain:** deb822 support in rewritePackageSources ([#61](https://github.com/trivoallan/houba/issues/61)) ([b8efe9f](https://github.com/trivoallan/houba/commit/b8efe9faf98c64e1fdc886508bb468c2f46debee))
* **reconcile:** retention-driven soft-delete (roadmap item 5) ([#63](https://github.com/trivoallan/houba/issues/63)) ([3fdbf95](https://github.com/trivoallan/houba/commit/3fdbf95860d68add79ca8c11bb4e74db1cbb9a2e))
* scan attestation — sign the houba attach referrer ([#56](https://github.com/trivoallan/houba/issues/56)) ([388e970](https://github.com/trivoallan/houba/commit/388e9701bd003e97db5b847856d1598b72871f7d))


### Bug Fixes

* **adapters:** cosign v3 signing-config migration (signing was broken on bundled cosign) ([#58](https://github.com/trivoallan/houba/issues/58)) ([4af77b4](https://github.com/trivoallan/houba/commit/4af77b45bb9c5fab93a0a166b335f5572cdea114))
* **use-case:** scope reconcile unmark cleanup to the axis being unmarked ([#64](https://github.com/trivoallan/houba/issues/64)) ([ff3a957](https://github.com/trivoallan/houba/commit/ff3a957db13f411b3705341250b766b973a11e22))


### Documentation

* **readme:** bring README + examples current with v0.5 ([#65](https://github.com/trivoallan/houba/issues/65)) ([4808315](https://github.com/trivoallan/houba/commit/4808315487f3397fd008c296740f6abaee0c2c24))
* **readme:** bring README current with v0.4 (commands, SLSA, autoscaling, arch) ([#60](https://github.com/trivoallan/houba/issues/60)) ([00d8946](https://github.com/trivoallan/houba/commit/00d89462b1b82d81e49cb764f6db7a9895336e11))
* **roadmap:** mark lifecycle ⑤ delivered and archive_restore rejected ([#66](https://github.com/trivoallan/houba/issues/66)) ([8bfd778](https://github.com/trivoallan/houba/commit/8bfd7786e17a88fbbea5f0fab48096986cdb194c))
* **specs:** buildkitd autoscaling design — KEDA-driven scale-up ([#43](https://github.com/trivoallan/houba/issues/43)) ([3046148](https://github.com/trivoallan/houba/commit/3046148b175f5ded87086082aad08a1bb1e0c529))

## [0.4.0](https://github.com/trivoallan/houba/compare/v0.3.0...v0.4.0) (2026-06-13)


### Features

* concurrent reconcile (scale-up) + horizontal sharding (scale-out) ([#37](https://github.com/trivoallan/houba/issues/37)) ([6cb2d29](https://github.com/trivoallan/houba/commit/6cb2d297996548a3b346739e2e36782d2552e1d2))
* coverage audit — houba audit (roadmap ④) ([#53](https://github.com/trivoallan/houba/issues/53)) ([248dd1a](https://github.com/trivoallan/houba/commit/248dd1a1cb567b4953489a07ceed4f667b6e0ba4))
* delegated tag deletion (soft-delete via OCI referrer, mode cascade) ([#41](https://github.com/trivoallan/houba/issues/41)) ([d8a0e43](https://github.com/trivoallan/houba/commit/d8a0e43ed3bef77faa5a506f06dc738e94257c9f))
* **deploy:** local-transform demo tier — self-contained rebuild path (no Harbor) ([#32](https://github.com/trivoallan/houba/issues/32)) ([a8954f5](https://github.com/trivoallan/houba/commit/a8954f57d47846d1759e5d3509cb98d8f13be68d))
* **deploy:** opt-in source-registry credentials to dodge Docker Hub rate limits ([#34](https://github.com/trivoallan/houba/issues/34)) ([a271fa1](https://github.com/trivoallan/houba/commit/a271fa15c9e337a0636554f3f8fa5bf58a6b832c))
* houba attach — ingest + stamp scan results as OCI referrers ([#42](https://github.com/trivoallan/houba/issues/42)) ([b2afcb6](https://github.com/trivoallan/houba/commit/b2afcb6c7e718a9336496efc9009b8c34c8f558d))
* houba purge — the reference reaper (usage-gated tag deletion) ([#45](https://github.com/trivoallan/houba/issues/45)) ([f52eaee](https://github.com/trivoallan/houba/commit/f52eaee3d65d18c449afb1db967b094a00714b06))
* **reconcile:** surface applied transform steps + produced digest per operation ([#38](https://github.com/trivoallan/houba/issues/38)) ([602247a](https://github.com/trivoallan/houba/commit/602247a31dacc8a4a97f268d51f194b6db8a8fce))
* SLSA / in-toto attestation — sign the rebuild path (roadmap ①) ([#49](https://github.com/trivoallan/houba/issues/49)) ([2c1b6e4](https://github.com/trivoallan/houba/commit/2c1b6e4d8e3feb3ac6666052b10080bd5a3b4f5c))


### Documentation

* align CLAUDE.md with the delivered hexagon + embed design/specs in the C4 workspace ([#35](https://github.com/trivoallan/houba/issues/35)) ([42c10af](https://github.com/trivoallan/houba/commit/42c10afa4234257a647b111f473fe5afe4a6b53e))
* **architecture:** add `attach` to the C4 model + finish the CLAUDE.md inventory ([#55](https://github.com/trivoallan/houba/issues/55)) ([0d3a634](https://github.com/trivoallan/houba/commit/0d3a6344b12cf0cd7be81229d45397e6f04eefd3))
* **architecture:** add ADRs for the 3 remaining specs (scale-up/-out, source creds) ([#40](https://github.com/trivoallan/houba/issues/40)) ([c06bde0](https://github.com/trivoallan/houba/commit/c06bde0db5fb9e30110540d1edabbba7f468864c))
* **architecture:** add C4 container/component/hexagon views, refresh stale docs ([#39](https://github.com/trivoallan/houba/issues/39)) ([9525fa6](https://github.com/trivoallan/houba/commit/9525fa6346bd7845d43ddde3e189ee1883a7a7b9))
* **architecture:** link each view / example name to its Mermaid export ([#46](https://github.com/trivoallan/houba/issues/46)) ([769c86f](https://github.com/trivoallan/houba/commit/769c86fb56e67550d694bab9051a7245d88cfb90))
* **architecture:** redraw the error hierarchy as Mermaid in design.md ([#48](https://github.com/trivoallan/houba/issues/48)) ([41ed446](https://github.com/trivoallan/houba/commit/41ed44652b524b5b83ecac40276e3fd7505648b2))
* **architecture:** redraw the hexagon schema as Mermaid in design.md ([#47](https://github.com/trivoallan/houba/issues/47)) ([d26648c](https://github.com/trivoallan/houba/commit/d26648c1812467bb13800b1566e10082c47d0d1b))
* **architecture:** split the deployment view into one per example + commit Mermaid exports ([#44](https://github.com/trivoallan/houba/issues/44)) ([91c4f8d](https://github.com/trivoallan/houba/commit/91c4f8d2f008d2cc413948d8ac8209a1fdc91343))
* sync design.md + roadmap with delivered work (CLI verbs, SLSA, new ports/adapters) ([#54](https://github.com/trivoallan/houba/issues/54)) ([4153b9e](https://github.com/trivoallan/houba/commit/4153b9e349477d2033efbe755c1ef8d51656f3c6))

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
