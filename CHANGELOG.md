# Changelog

## 0.1.0 (2026-06-11)


### Features

* **adapter:** implémente les 7 méthodes write de HarborHttpAdapter ([38ed2c7](https://github.com/trivoallan/houba/commit/38ed2c7ab6ba952ac4e1eeb25a867badb181817c))
* **adapters:** BuildkitAdapter wrap buildctl avec fake-bin de test ([e3ab03e](https://github.com/trivoallan/houba/commit/e3ab03ece4b010fb5bfb53f09ca5975caf785d22))
* **adapters:** EndoflifeHttpAdapter (parse JSON, retry transient) ([118f245](https://github.com/trivoallan/houba/commit/118f24519e8fe8766b462b04edc5db180336f6f7))
* **adapters:** GitCliAdapter wrap git CLI avec fake-bin de test ([24d8283](https://github.com/trivoallan/houba/commit/24d82836b8d5996ec8b2fc5f45ec745841ab4dd9))
* **adapters:** GitLabHttpAdapter pour API REST GitLab (find/MR/variable) ([0066031](https://github.com/trivoallan/houba/commit/0066031cadacd1db3d8a8c2072f06d374998b70b))
* **adapters:** HarborHttpAdapter ajoute get_artifact / list_artifact_tags / list_immutable_tag_rules ([1b0a901](https://github.com/trivoallan/houba/commit/1b0a901809d8b7ed3703b7eee1731d5c6776c216))
* **adapters:** TeamsWebhookAdapter (POST JSON avec retry transient) ([90374f6](https://github.com/trivoallan/houba/commit/90374f64866c5ac25e568bce73afdb488d69b47b))
* **cli:** étend le composition root avec les 5 nouveaux adapters Phase B ([b574ded](https://github.com/trivoallan/houba/commit/b574ded7b0f8235e90f07d3756570a3086259017))
* **config:** ajoute HOUBA_LABEL_PREFIX (défaut io.houba) pour générifier les labels OCI ([81da270](https://github.com/trivoallan/houba/commit/81da2701e46b8d8876e4e68ea58f8739121cf4d6))
* **domain:** enveloppe MirrorPolicy + parse_mirror_policy ([8f40b51](https://github.com/trivoallan/houba/commit/8f40b517fdf32a5aa631212c53c609b5e8d7fee8))
* **domain:** export JSON Schema du MirrorPolicy (by_alias) ([927ad37](https://github.com/trivoallan/houba/commit/927ad370287beed754d4e289e34b21726de159e9))
* **domain:** MirrorPolicy Archive + Variant ([5ca95d3](https://github.com/trivoallan/houba/commit/5ca95d31af89f3065f6287e390d6592e027f09ba))
* **domain:** MirrorPolicy base — CamelModel, Source, Destination, ArtifactType ([2e02367](https://github.com/trivoallan/houba/commit/2e023679d6c960624664b0fd15b8c34725221869))
* **domain:** MirrorPolicy Defaults + ImportProfile ([b5949fa](https://github.com/trivoallan/houba/commit/b5949fa0b99d71d3613b4a4e26cbee1718fb49c8))
* **domain:** MirrorPolicy Spec + règle generic⇒no-transform ([d889d9f](https://github.com/trivoallan/houba/commit/d889d9f2948577f36d1b0553f3d6482c868f21c6))
* **domain:** MirrorPolicy TagSelection (regex/semverOnly/names/aliases) ([4981835](https://github.com/trivoallan/houba/commit/4981835e7d21235944922bf393e1d53df5f1632e))
* **domain:** MirrorPolicy TransformStep (parsing map single-clé) ([a2d382a](https://github.com/trivoallan/houba/commit/a2d382a0740e11376709ffd506803abe0e45c7ac))
* **domain:** rejette transform + multi-plateforme (rebuild différé) ([dc29957](https://github.com/trivoallan/houba/commit/dc299577533a29f7f58bd5fddb5cb41186f6d98b))
* **domain:** resolve_imports — merge defaults→import (règle B) ([a99d4c6](https://github.com/trivoallan/houba/commit/a99d4c6eb7144a7e9258a109b13bf3695e50fe14))
* **errors:** ajoute PolicyValidationError (branche DomainError) ([3dce65e](https://github.com/trivoallan/houba/commit/3dce65e63f0e0731c130ec7dcd46ca5ebfccd79d))
* **image:** runtime complète avec skopeo + buildctl + git (Phase B) ([786f7f5](https://github.com/trivoallan/houba/commit/786f7f5e3c7626f8fea0de294ebd1d3f833ae5ee))
* **ports:** ajoute EolSourcePort + FakeEolSourcePort ([d636707](https://github.com/trivoallan/houba/commit/d6367076e9188ec62d85890ef9fdb8075ebf8d77))
* **ports:** ajoute GitLabPort + FakeGitLabPort ([44c429a](https://github.com/trivoallan/houba/commit/44c429abe54f90aa0a39a101fe3743de41aebb1f))
* **ports:** ajoute GitRepoPort + FakeGitRepoPort ([7f7c6cb](https://github.com/trivoallan/houba/commit/7f7c6cb11eda1c57985195ee844f1b83d724b04a))
* **ports:** ajoute ImageBuilderPort + FakeImageBuilder ([cbb0325](https://github.com/trivoallan/houba/commit/cbb0325d1b9f4564fdc8a650c65a9625d3e163bf))
* **ports:** ajoute NotifierPort + FakeNotifierPort ([750b886](https://github.com/trivoallan/houba/commit/750b8861e414f51dafb7e4bcb856365fdfdc33d4))
* **ports:** étend HarborPort avec dataclasses et méthodes write ([265c33c](https://github.com/trivoallan/houba/commit/265c33ce9210f3fdc4289a5c1975659c5edcbabc))


### Bug Fixes

* **adapter:** empty-body guard sans data-loss + assert sur ensure_label ([84ec7e8](https://github.com/trivoallan/houba/commit/84ec7e861e27b1deea2b7791b2f9a806e82c2af6))
* **ci:** load: true sur docker build pour le smoke test ([61157f2](https://github.com/trivoallan/houba/commit/61157f2a7ad42405023efea0228cc67472aa89cc))
* **domain:** archive shallow-merge (règle B) + durcissements revue Phase 1 ([d8f81eb](https://github.com/trivoallan/houba/commit/d8f81ebb270ef16fec23cdb4d6c56220922aec01))
* **domain:** build_plan default label_prefix=io.houba (était SNCF-specific) ([1e64706](https://github.com/trivoallan/houba/commit/1e64706c5d601f93a1e9fc8f9d33f7074b409eff))
* **rename:** h2h résiduel en fin de docstring (CLI h2h.) ([e5053fb](https://github.com/trivoallan/houba/commit/e5053fb96f8ef9f894892a18c3411cd5587d664b))


### Documentation

* **adapter:** commente la convention safe=":" sur les digests Harbor ([1f3b1d9](https://github.com/trivoallan/houba/commit/1f3b1d980b2fc54af406a54518084fd5693850d8))
* ajoute CLAUDE.md (guidance Claude Code) ([5bb9823](https://github.com/trivoallan/houba/commit/5bb9823cdb63ac34f701ac1820e49f6c3573bb3d))
* CLAUDE.md — JSON Schema systématique pour tout contrat déclaratif ([148ffb7](https://github.com/trivoallan/houba/commit/148ffb7520047217804a873ec3e5fe80c1dc6fe6))
* nettoyage radical pour publication publique ([4abe306](https://github.com/trivoallan/houba/commit/4abe306fff16050cf11e6c06be7f4729f91abb6c))
* **plan:** plan d'implémentation Phase B (adapters + image v0-rc) ([e0fa988](https://github.com/trivoallan/houba/commit/e0fa9880980213721f4182f9390359a113c3b51a))
* **plans:** plan Phase 1 MirrorPolicy (schéma + merge + JSON Schema) ([dc17081](https://github.com/trivoallan/houba/commit/dc17081b8e949c53f9385281c2d07278534b67d4))
* README pour publication GitHub publique ([6850882](https://github.com/trivoallan/houba/commit/68508820aa12fee927340380f8c3362c764cc07b))
* repositionne houba en "stamper / porte d'entrée" + roadmap Phase C ([d27bacf](https://github.com/trivoallan/houba/commit/d27bacf7b383e1557d20bc9c2ad32d222d5a5230))
* **specs:** adopte regctl comme client registry (remplace skopeo) ([ebd0e17](https://github.com/trivoallan/houba/commit/ebd0e17e0ca76678d5accbcf33b7a5c2b40fd129))
* **specs:** conception du format MirrorPolicy + contrat reconcile ([1c0dbe2](https://github.com/trivoallan/houba/commit/1c0dbe2d33b8d184a9ecb1ad1a04d0a9b7b1af7b))
* **specs:** gère le multi-arch (copy path d'abord) ([5fb13bf](https://github.com/trivoallan/houba/commit/5fb13bffdfb8186c7c475ac93c0835aa762e6309))
* **specs:** tranche 3 points de revue (artifactType requis, alias=erreur, load récursif) ([3497af8](https://github.com/trivoallan/houba/commit/3497af84d265197f4207b30904c8643dd7f0e2b1))
