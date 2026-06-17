# Changelog

## [0.7.0](https://github.com/trivoallan/houba/compare/v0.6.0...v0.7.0) (2026-06-17)


### Features

* attach registry-config parity — wire HOUBA_REGISTRIES into `houba attach` ([#97](https://github.com/trivoallan/houba/issues/97)) ([c320179](https://github.com/trivoallan/houba/commit/c3201790552a85985e47daa215cbd4d001e0b737))
* **audit:** digest on every coverage outcome + observational --sbom tier ([#143](https://github.com/trivoallan/houba/issues/143)) ([522b764](https://github.com/trivoallan/houba/commit/522b764ce5251daf886cd488657e28b1e71b2173))
* **deploy:** default argocd-prod policy to the bundled busybox example ([014cb95](https://github.com/trivoallan/houba/commit/014cb95be45b8c69658b3c3ea2fd88c4012da62b))
* **deploy:** default overlays/prod policy to the busybox example ([#87](https://github.com/trivoallan/houba/issues/87)) ([208bd85](https://github.com/trivoallan/houba/commit/208bd85562c7382c3d7aec18eea48025963a43b7))
* **deploy:** Dependency-Track consumer + XZ (CVE-2024-3094) incident demo for package-level blast-radius ([#136](https://github.com/trivoallan/houba/issues/136)) ([b1b2034](https://github.com/trivoallan/houba/commit/b1b203464003db725445c0962b63e2f74b4b486c))
* **deploy:** make argocd-prod + argocd-seed (bring up the full prod App-of-Apps on kind) ([59b69f2](https://github.com/trivoallan/houba/commit/59b69f2eb1c2466dfc8c9e81715ffb594c0933d8))
* **deploy:** make argocd-prod a complete end-to-end mirror on kind ([76ac75b](https://github.com/trivoallan/houba/commit/76ac75be6b9618dcf5cb54db40728a1fa508949c))
* **deploy:** weekly houba-gc CronJob in the reference deployment ([#107](https://github.com/trivoallan/houba/issues/107)) ([a06d171](https://github.com/trivoallan/houba/commit/a06d171e102f77933730b9ad487e1f8b91267978))
* **deploy:** Zot demo registry with built-in UI; text logs in Jobs ([#92](https://github.com/trivoallan/houba/issues/92)) ([21dc7bd](https://github.com/trivoallan/houba/commit/21dc7bdf4ac1a1c5a2842142ac26fc65ac749163))
* **domain:** stamp OCI image.title and configurable vendor ([#134](https://github.com/trivoallan/houba/issues/134)) ([1253d70](https://github.com/trivoallan/houba/commit/1253d703902ae7a208f47c5b49d5d73492f209db))
* finding-type-aware SARIF mapper (rule evaluations ≠ vulnerabilities) ([#102](https://github.com/trivoallan/houba/issues/102)) ([3aee05b](https://github.com/trivoallan/houba/commit/3aee05be6e5d5ba9d537c6f62548904bbcfae14a))
* houba attach --fail-on &lt;severity&gt; CI gate ([#86](https://github.com/trivoallan/houba/issues/86)) ([f0cf0bc](https://github.com/trivoallan/houba/commit/f0cf0bcd2a7389a421789ce192d676eecf9e8275))
* multi-owner ownership (io.houba.owners) ([#100](https://github.com/trivoallan/houba/issues/100)) ([139f7b1](https://github.com/trivoallan/houba/commit/139f7b11f26fc3bff5ac717bac499970a08a50c2))
* SBOM generation on the rebuild path (package-level blast-radius) ([#128](https://github.com/trivoallan/houba/issues/128)) ([003f0b8](https://github.com/trivoallan/houba/commit/003f0b85bded244cc3621ea0da55d779dfd6f391))
* scan-referrer garbage collection (houba gc) ([#105](https://github.com/trivoallan/houba/issues/105)) ([b9892d6](https://github.com/trivoallan/houba/commit/b9892d626b24e867496332fe7f15dfcef0019991))
* sign the SBOM under houba's identity (trust tier) ([#144](https://github.com/trivoallan/houba/issues/144)) ([f2fec80](https://github.com/trivoallan/houba/commit/f2fec80ff2c1aa23ec3417e677aac46abc99ee96))
* signed-coverage audit tier (houba audit --signed) ([#98](https://github.com/trivoallan/houba/issues/98)) ([3e4336d](https://github.com/trivoallan/houba/commit/3e4336d4347704652821a2583f45fc3246c3fd07))
* unify SBOM generation on syft — both paths, SPDX + CycloneDX ([#140](https://github.com/trivoallan/houba/issues/140)) ([eec9aa2](https://github.com/trivoallan/houba/commit/eec9aa2caa07437fc7297dd2599d6051041f188a))


### Bug Fixes

* **.claude:** point superpowers at its own marketplace so it loads in ephemeral sessions ([#94](https://github.com/trivoallan/houba/issues/94)) ([578601d](https://github.com/trivoallan/houba/commit/578601d53a95fa8abf6b7239e1582c93363e73c2))
* **adapters:** honor tls_verify on the BuildKit push path ([#127](https://github.com/trivoallan/houba/issues/127)) ([118ec54](https://github.com/trivoallan/houba/commit/118ec548e226e53afc3323a974bf3cd206c05b74))
* **ci:** update the manifests job for the single Argo app set ([#91](https://github.com/trivoallan/houba/issues/91)) ([ee1cad9](https://github.com/trivoallan/houba/commit/ee1cad904b7d7c7c4c1790aa761750f042a2ac90))
* **cli:** render failed policy with only operation errors ([#126](https://github.com/trivoallan/houba/issues/126)) ([36efafd](https://github.com/trivoallan/houba/commit/36efafd6919e490e4ef8522786786441ee64c170))
* demo reference policy/rebuild — busybox tag selection + arch-robust inspect ([#139](https://github.com/trivoallan/houba/issues/139)) ([51e8bc1](https://github.com/trivoallan/houba/commit/51e8bc1fd6baab748cc85841efd8693485ed5b27))
* **deploy:** select the OpenBao server pod by name, not a chart label ([#88](https://github.com/trivoallan/houba/issues/88)) ([16d4c56](https://github.com/trivoallan/houba/commit/16d4c56c8f8d94e5aab605eee71b7ad7fe784348))
* **deps:** clear docs-site high/uuid CVEs — bump Docusaurus + pin transitives ([a5a9c20](https://github.com/trivoallan/houba/commit/a5a9c20074acdf45cb1a5b87a3c40cde3eb12047))
* **deps:** update react monorepo to v19 ([#138](https://github.com/trivoallan/houba/issues/138)) ([1d78def](https://github.com/trivoallan/houba/commit/1d78defd8c67a4615d27d20c361bc5098c59ef3a))


### Documentation

* add "Why houba" argument page ([#104](https://github.com/trivoallan/houba/issues/104)) ([0dbffb9](https://github.com/trivoallan/houba/commit/0dbffb97682c7fe06b1300b9ff28214e36bdc779))
* add the CLI command reference to the reference section ([#125](https://github.com/trivoallan/houba/issues/125)) ([786b412](https://github.com/trivoallan/houba/commit/786b412b775c1a6adac86ad8b483c39472892554))
* **docs:** mark Now items delivered; renumber signed-coverage ADR to 0026 ([#99](https://github.com/trivoallan/houba/issues/99)) ([ff5fdea](https://github.com/trivoallan/houba/commit/ff5fdea279d899e5856ed902c6f8401f026ae539))
* fix the generated reference's in-page TOC anchors ([#121](https://github.com/trivoallan/houba/issues/121)) ([3cf1ffb](https://github.com/trivoallan/houba/commit/3cf1ffbbb09345a4c427d57ab93defc30b6d12d8))
* generate how-to & explanation section indexes from page front-matter ([#147](https://github.com/trivoallan/houba/issues/147)) ([b88f452](https://github.com/trivoallan/houba/commit/b88f4526251bb93047f220e869aeb13074be05b0))
* generate policy + config reference from the Pydantic schemas ([#108](https://github.com/trivoallan/houba/issues/108)) ([f8e52b7](https://github.com/trivoallan/houba/commit/f8e52b7bd6234d1aa2d199d26909343974547180))
* generate policy + config reference from the Pydantic schemas ([#109](https://github.com/trivoallan/houba/issues/109)) ([28651c2](https://github.com/trivoallan/houba/commit/28651c28581774990b5e25ad80b28f0b08eefb1d))
* order the Reference sidebar — mirror-policy before config ([#120](https://github.com/trivoallan/houba/issues/120)) ([cb35be0](https://github.com/trivoallan/houba/commit/cb35be0977677dd193b6774dd32c46ac835977ea))
* order, label, and flatten the docs-site sidebar ([#118](https://github.com/trivoallan/houba/issues/118)) ([f7cb370](https://github.com/trivoallan/houba/commit/f7cb370188cc43c12f973549cf2ae3f058c42e0b))
* prepare 0.7.0 release — stamp roadmap + getting-started version ([2daebf9](https://github.com/trivoallan/houba/commit/2daebf9679ba2c04fe5e3499c9b8a9d4c19e3c1b))
* promote the local walkthrough to a top-level Getting started ([#106](https://github.com/trivoallan/houba/issues/106)) ([ba91bf9](https://github.com/trivoallan/houba/commit/ba91bf901dbdbd9c83a86666df8847683dd0c50b))
* publish the docs site with Docusaurus on GitHub Pages ([#115](https://github.com/trivoallan/houba/issues/115)) ([3e5eba3](https://github.com/trivoallan/houba/commit/3e5eba3d6c47ec4d357a8ac08fff6d34e86e8359))
* record the Dependency-Track boundary (attach = scan provenance, not a store) ([#135](https://github.com/trivoallan/houba/issues/135)) ([28af8a4](https://github.com/trivoallan/houba/commit/28af8a47f5099fab4d3a5a2f4d726356a4e7f5e8))
* refresh README for the delivered mandate, gc, and the docs site ([#110](https://github.com/trivoallan/houba/issues/110)) ([10a92cb](https://github.com/trivoallan/houba/commit/10a92cbc9b221cc71ff834d89caef739663c3dd6))
* renumber duplicate ADR 0026 → 0030 (multi-owner ownership) ([#122](https://github.com/trivoallan/houba/issues/122)) ([cab739c](https://github.com/trivoallan/houba/commit/cab739c4f607e9e199421cdbe6a589f1a7390801))
* restructure docs into Diátaxis sections (step 1 — folders + moves) ([#111](https://github.com/trivoallan/houba/issues/111)) ([1009b72](https://github.com/trivoallan/houba/commit/1009b72f1f64b18826724cc422b0eb0e3a099f01))
* restructure docs into Diátaxis sections (step 1) ([#112](https://github.com/trivoallan/houba/issues/112)) ([c0c52cd](https://github.com/trivoallan/houba/commit/c0c52cd004fd1b4c263a01eed073a01fa66e69c0))
* roadmap — add docs-site item, cut deferred bets, proxycache out of scope ([#103](https://github.com/trivoallan/houba/issues/103)) ([5685732](https://github.com/trivoallan/houba/commit/5685732c1c8cffe8cdb90efab252e4725efc399b))
* **roadmap:** sync Now/Next/Later — the mandate is delivered ([#90](https://github.com/trivoallan/houba/issues/90)) ([e3de9ad](https://github.com/trivoallan/houba/commit/e3de9ad769a381ad6f55350e9ea24ba4b181b68b))
* scan attestation max-age freshness contract (admission gate) ([#137](https://github.com/trivoallan/houba/issues/137)) ([5fc046b](https://github.com/trivoallan/houba/commit/5fc046bff8320fe318c0c68524dc0b7424f7f2f8))
* spec — Docusaurus docs site published to GitHub Pages ([#114](https://github.com/trivoallan/houba/issues/114)) ([335d459](https://github.com/trivoallan/houba/commit/335d459c7ebe96aa39e27874cdad38349b2cf250))
* split the examples mega-doc into how-to + explanation (step 2) ([#113](https://github.com/trivoallan/houba/issues/113)) ([fbf7db8](https://github.com/trivoallan/houba/commit/fbf7db8225d2038d5a2c7db1a2296ae4cec7c5ad))
* sync getting-started + architecture overview with shipped state ([#101](https://github.com/trivoallan/houba/issues/101)) ([04f0669](https://github.com/trivoallan/houba/commit/04f0669b02c248b2e85c0c5962ea173b3383fdd9))
* sync README/roadmap/design with shipped SBOM, gc, and docs site ([#146](https://github.com/trivoallan/houba/issues/146)) ([8e3fc88](https://github.com/trivoallan/houba/commit/8e3fc88cfc271e1083e912450d6aa9c0a2c727f6))

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
