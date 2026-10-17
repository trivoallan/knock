Sections arc42 touchées : aucune. Aucun bloc, conteneur ni frontière de déploiement ne se déplace. Un verbe CLI de plus, dans les couches existantes.

## Context

La motivation est dans `proposal.md` et les exigences dans `specs/policy-lint/spec.md`. Ce document tranche le *comment*.

État actuel, lu dans le code :

- `use_cases/loader.py:load_policy_dir` parcourt l'arbre et lève `PolicyValidationError` au **premier** fichier fautif. `domain/mirror_policy.py:parse_mirror_policy` enveloppe la `ValidationError` Pydantic en `PolicyValidationError(str(e))`, ce qui perd la localisation structurée (`loc`).
- La fusion des defaults (`domain/policy_merge.py:resolve_imports`) est pure.
- Les références à la configuration se résolvent par `config.resolve_registry`, `resolve_ca_certs` et `resolve_mirror`. Ces fonctions sont pures sur une roster, mais `resolve_ca_certs` est suivie d'une lecture de fichier CA dans `reconcile_registry._read_cert_file`.
- Les collisions d'alias (`domain/collision.py:detect_alias_collisions`) se calculent sur des `AliasTarget(dest_repo, alias, target)` **rendus**. Côté registre, ils viennent de `resolve_aliases(templates, concrete_tags)`, donc des tags amont. Côté git, `alias = src.ref`, et le planner lit les tags de destination. Hors ligne, on ne dispose que des **gabarits**.
- Convention de sortie (ADR 0003, ADR 0014, `cli/audit.py`) : rapport machine sur stdout, journal sur stderr. Le format est choisi par `KNOCK_LOG_FORMAT` (`text` par défaut, `json`). Le schéma du rapport est dérivé du modèle et publié par `scripts/gen_reference.py`.

ADR en vigueur qui contraignent ce design : 0001 (modèles Pydantic comme source unique, schéma dérivé), 0003 (deux flux, rapport publié), 0014 (un verbe en lecture seule qui émet un rapport versionné). Aucun n'est remis en cause.

## Goals / Non-Goals

**Goals :**

- Valider un arbre de politiques **sans réseau, sans outils externes et sans conteneur DI**, avec la seule `Settings` pour N3.
- Garantir que lint et reconcile rendent le même verdict de chargement N1 : il n'y a qu'**un** chemin de parsing.
- Collecter toutes les erreurs, avec le fichier et la localisation.

**Non-Goals :**

- Prédire le rendu des alias à partir des tags réels : c'est le rôle de `reconcile --plan-out`.
- Valider un fichier isolé, SARIF, ou un mode `--fix`/formatage.
- Changer le comportement de chargement de `reconcile` et `promote`.

## Decisions

### D1. Un chargeur collecteur, et `load_policy_dir` devient son enveloppe

`load_policy_files(dir) -> (list[LoadedPolicy], list[Finding])`, où `LoadedPolicy` porte le chemin relatif et la `MirrorPolicy`. `load_policy_dir` l'appelle et lève sur le premier `Finding`, avec le même message préfixé du chemin qu'aujourd'hui.

*Pourquoi ainsi :* un seul parcours et un seul parsing, ce qui garantit l'exigence « même verdict que reconcile ». *Alternative écartée :* un second parcours propre à lint. Deux boucles qui divergeront au premier ajout de règle (extension de fichier, fichiers cachés).

### D2. `PolicyValidationError` porte ses localisations

`parse_mirror_policy` garde sa signature et son comportement. L'exception gagne un attribut `issues: list[tuple[loc, message]]`, rempli depuis `ValidationError.errors()`. Pour YAML invalide ou racine non mapping, il contient un seul élément sans `loc`. Le `str()` reste celui d'aujourd'hui. Les erreurs transversales levées par les validateurs de modèle de `Spec` sont des `PolicyValidationError` nus : elles ne portent aucune `loc`, seulement le message. Un fichier illisible devient une anomalie de lint, alors que `reconcile` le relève comme avant.

*Alternative écartée :* que lint appelle `MirrorPolicy.model_validate` lui-même. Cela dupliquerait le prétraitement YAML et casserait l'unicité du chemin (D1).

### D3. Le littéral se reconnaît à l'absence de `{`

Un alias est **littéral** s'il ne contient aucun `{`. `latest` est donc littéral, bien que `resolve_aliases` le traite comme cas spécial : son *nom* est fixe, et c'est le nom qui collisionne. Pour une source git, l'alias est la `ref` de la source, donc littéral.

La détection passe dans le domaine sous la forme d'une fonction collectrice, `find_alias_overlaps(claims) -> list[AliasOverlap]`. Les entrées sont `(dest_repo, alias, origin)`, où `origin` est le nom de l'import. Chaque overlap est classé `certain` (deux littéraux identiques) ou `possible` (deux gabarits). `detect_alias_collisions` reste inchangé pour reconcile, qui travaille sur des alias rendus.

*Alternative écartée :* rendre les gabarits sur un jeu de tags synthétique. On obtient des faux positifs et négatifs invérifiables, et une logique plus lourde que le contrôle qu'elle prétend affiner.

*Limite assumée :* un gabarit et un littéral qui pourraient se rejoindre (`{major}` et `1`) ne sont pas signalés. Une collision réelle reste attrapée par `reconcile`, avant toute mutation.

*Portée, corrigée pendant l'implémentation :* `reconcile` refuse déjà que deux politiques de `metadata.name` différent écrivent dans le même dépôt (`detect_dest_repo_collisions`, appelée dans `use_cases/reconcile.py` ; c'est l'invariant qui rend le sharding sûr). Lint reprend cette règle telle quelle, en erreur N2, avec la même fonction sur des paires `(dépôt, nom de politique)` ; il la collecte au lieu de lever. Les chevauchements d'alias ne se comparent donc qu'**entre imports d'une même politique** : entre deux politiques, le partage du dépôt est déjà une erreur, et un avertissement de gabarit y serait du bruit. Avertir là où `reconcile` refuse aurait laissé passer en vert un arbre que le screening rejette.

### D4. La clé de dépôt dépend de N3

Une collision se juge par dépôt de destination. Sans roster, le registre logique ne peut pas se résoudre en hôte. La clé devient alors `(nom de registre ou "<défaut>", project, repository)`, à partir du nom logique. Avec la roster, la clé est l'hôte résolu, comme `_resolved_dest_repos` le fait déjà. Deux noms logiques qui désignent le même hôte ne sont donc rapprochés qu'avec N3.

### D5. N3 sans conteneur DI

`knock lint` construit `Settings()` seul, sans `build_container()`. Une `Settings` invalide donne exit 3, par le mapping de `cli/main.py`. N3 s'exécute si et seulement si `settings.registries` est non vide. Il appelle `resolve_registry`, `resolve_ca_certs` et `resolve_mirror` sur chaque référence, et tente de lire chaque fichier CA référencé. Chaque `ConfigError` levée devient un `Finding` rattaché au fichier de politique, pas un exit 3 : c'est la *politique* qui référence un nom absent.

*Distinction tenue :* une configuration illisible donne exit 3. Une politique qui référence ce que la configuration n'a pas donne une erreur de lint, donc exit 1.

### D6. Le format suit `KNOCK_LOG_FORMAT`, comme `knock audit`

Le rapport est émis en JSON quand `KNOCK_LOG_FORMAT=json`, en texte sinon. La CI du dépôt de politiques pose `KNOCK_LOG_FORMAT=json`.

*Pourquoi :* c'est la convention de tous les verbes à rapport (ADR 0003, `audit`). Un `--format` propre à lint en ferait une exception. **Ce choix corrige la spec**, qui prévoyait « JSON par défaut, `--format text` ». L'exigence correspondante est réécrite dans la même passe.

### D7. Le modèle du rapport et sa publication

`LintReport` (Pydantic) : `apiVersion: knock.io/v1alpha1`, `kind: LintReport`, `errors[]`, `warnings[]`, `skipped[]`. Un `Finding` porte `level` (`N1`/`N2`/`N3`), `path`, `loc` (optionnel), `message` et `related` (les autres chemins, pour les collisions). `skipped` liste les niveaux non exécutés, avec leur raison. Le schéma est dérivé et ajouté à `scripts/gen_reference.py`, donc couvert par la dérive que `make lint` contrôle déjà.

### D9. Les étapes de transformation se valident en N2, sans configuration

`TransformStep.params` est un `dict` libre au chargement. Le nom de l'étape (`DEFAULT_REGISTRY.get`) et ses paramètres (`compiler.policy_model().model_validate`) ne sont vérifiés qu'au plan de `reconcile`, dans `_resolve_transform` et `_resolve_remediation` (`use_cases/reconcile_registry.py`). Lint fait la même vérification, sur les étapes résolues de chaque import et de chaque variante, avec le même registre et le même modèle. Il en tire au passage les `resource_refs` dont N3 a besoin.

*Pourquoi en N2 :* c'est pur, et c'est la faute de frappe la plus probable d'un auteur de politique. *Alternative écartée :* déplacer cette validation dans le modèle `MirrorPolicy`. Ça changerait le moment où `reconcile` refuse une politique, ce que D1 exclut, et ça mérite sa propre change.

### D8. Le code de sortie se dérive des findings

`lint_exit_code(report)` vaut 0 sans erreur et 1 sinon. L'exit 3 ne vient que de la configuration illisible (D5), par la voie existante. Aucune nouvelle classe d'erreur n'est nécessaire : les findings sont des données, pas des exceptions.

## Risks / Trade-offs

- [Le chargeur partagé change le message de `reconcile`] -> D1 garde le texte actuel. Un test existant de `load_policy_dir` sert de garde-fou.
- [Les avertissements de gabarits sont bruyants sur un gros dépôt où plusieurs politiques visent volontairement un même dépôt] -> Ils n'échouent jamais. Si le bruit gêne, on ajoutera une exemption explicite plus tard, pas maintenant.
- [Collisions manquées sans N3 (D4) ou entre gabarit et littéral (D3)] -> `reconcile` reste le filet, et la limite est écrite dans la référence CLI.
- [Une lecture de fichier CA sur le poste de CI qui n'a pas les mêmes chemins que la production] -> Un fichier CA absent est une erreur N3. Une CI qui ne monte pas les CA n'a qu'à ne pas définir `KNOCK_REGISTRIES`. Le saut est alors tracé.

## Migration Plan

Le changement est additif : un verbe nouveau, et aucun format ni comportement existant ne change. Pour revenir en arrière, on retire le verbe. Le chargeur partagé (D1) garde le comportement de `load_policy_dir`.

## Open Questions

1. La CI de `docs/` (`docs/policies/`) devrait-elle adopter `knock lint` ? Ce serait une change dans le dépôt `docs`, hors de celle-ci.
2. `reconcile` sur un répertoire absent ou sans politique ne fait rien, et ne le signale pas (revue n° 2). Pointé sur la racine d'un dépôt, il lit aussi les YAML de CI (revue n° 6). Faut-il durcir le chargeur partagé, au risque de changer `reconcile` ?
3. Des numéros de ligne dans les findings, pour les annotations de MR (revue n° 4) : faut-il un chargeur YAML qui garde les marques de nœuds ?
4. Unicité de `metadata.name` dans un arbre (revue n° 7) : faut-il l'imposer à `reconcile` et à `lint` ensemble ?
