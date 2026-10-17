# Proposition — valider un arbre de MirrorPolicy hors ligne, avant le merge

## Why

Aujourd'hui, une MirrorPolicy n'est validée qu'au moment où `knock reconcile` (ou `promote`) charge le répertoire. Il faut alors la configuration `KNOCK_*`, les outils, et les registres, parce que la phase de plan les lit. De plus, le chargeur s'arrête au premier fichier fautif. La CI d'un dépôt de politiques, qui en porte des milliers, n'a aucun moyen léger de refuser une politique cassée avant le merge. Elle découvre l'erreur au screening suivant, dans un `reconcile` qui échoue en entier.

Le JSON Schema publié (`docs/reference/schemas/mirror-policy.schema.json`) ne couvre qu'une partie du problème. Il ne voit ni les `model_validator` du modèle, ni la fusion de `defaults` dans les imports, ni les collisions entre politiques.

## What Changes

- Nouveau verbe **`knock lint <dir>`**. Il est en lecture seule, hors ligne, et parcourt l'arbre complet (les collisions sont un contrôle entre politiques, donc on ne valide pas un fichier isolé).
- Trois niveaux de contrôle, et **toutes** les erreurs sont collectées, pas seulement la première :
  - **N1**, sur chaque fichier : YAML bien formé, racine en mapping, modèle `MirrorPolicy`, validateurs sémantiques compris.
  - **N2**, sur l'arbre : fusion de `defaults` dans chaque import, et collisions d'alias **certaines**, c'est-à-dire le même alias littéral (sans `{…}`, `latest` par exemple) écrit dans le même dépôt de destination par deux imports. Les gabarits qui visent un même dépôt sont rapportés en **avertissement**, car leur rendu dépend des tags amont, inconnus hors ligne.
  - **N3**, contre la configuration : registre de destination, `caCert` et miroir de paquets inconnus, fichier CA illisible. Ce niveau est **implicite**. Il s'exécute si `KNOCK_REGISTRIES` est défini, et sinon il est sauté. Le saut est tracé dans la sortie et ne fait pas échouer.
- Sortie **JSON** sur stdout sous `KNOCK_LOG_FORMAT=json` (texte sinon, comme `knock audit`) : `errors`, `warnings` et `skipped`. Chaque entrée porte le chemin du fichier, la localisation dans la politique et le message. Le contrat est publié comme schéma sous `docs/reference/schemas/`, dans la même lignée que `coverage-report`.
- Codes de sortie, dérivés de la hiérarchie existante : `0` si aucune erreur (avec ou sans avertissements), `1` si au moins une erreur de politique, `3` si la configuration fournie est illisible.
- `load_policy_dir` garde son comportement d'échec immédiat. Il s'appuie sur le nouveau chargeur collecteur, donc `reconcile` et `promote` ne changent pas.

## Alternatives écartées

- **Ne rien faire, avec `check-jsonschema` en CI.** Ça ne couvre que N1, et en partie seulement : les validateurs sémantiques, la fusion des defaults et les collisions restent invisibles avant le screening.
- **Enrichir le JSON Schema au lieu d'écrire une commande.** Une collision entre deux fichiers ne s'exprime pas en JSON Schema, et dupliquer les validateurs Pydantic dans le schéma créerait une seconde source de vérité.
- **`reconcile --validate-only`.** Ça réutilise toute la phase de plan, mais `planner.plan()` lit les registres (les tags amont pour les alias, les tags de destination pour le chemin git). On perd le hors-ligne, qui est la raison d'être de la commande.
- **Les noms `knock validate` et `knock policy check`.** `validate` est trop proche de `verify`, qui rend un verdict sur un digest. Un sous-typer `policy` prépare des verbes que personne n'a demandés.
- **N3 sur flag explicite (`--with-config`).** Une CI sans roster devrait le savoir pour ne pas le passer. L'exécution implicite avec saut tracé dit la même chose sans option de plus.
- **Collisions possibles en erreur, ou ignorées.** En erreur, la CI échouerait sur des chevauchements de gabarits que les tags réels ne produiront peut-être jamais. Ignorées, on tairait un risque que l'on sait détecter.
- **Valider un fichier isolé.** Ça manquerait les collisions avec les politiques déjà mergées.
- **Une sortie SARIF.** Aucune plateforme de MR ne la demande aujourd'hui. On l'ajoutera quand une le demandera.

## Conception

Conception : due. Deux conditions s'appliquent. D'abord, une ambiguïté à lever avant le code : distinguer un alias littéral d'un gabarit, et cerner ce que N2 peut affirmer sans les tags (chemins registre et git). Ensuite, un modèle de données nouveau : le contrat JSON de sortie, publié comme schéma.

## Revue

Revue : due. Le changement livre une surface face à un tiers, un nouveau verbe CLI et un contrat JSON consommé par la CI du dépôt de politiques.

Objectif qualité : aucun déclaré (arc42 absent ou sans objectifs qualité).

## Capabilities

### New Capabilities

- `policy-lint` : validation hors ligne d'un arbre de MirrorPolicy, avec ses niveaux N1/N2/N3, la collecte de toutes les erreurs, son contrat de sortie JSON et ses codes de sortie.

### Modified Capabilities

Aucune. `reconcile` garde son chargement en échec immédiat, et aucune exigence des specs existantes ne change.

## Impact

- `knock/cli/` : nouveau `lint.py`, enregistré dans `main.py`. `docs/reference/command-line-interface.md` est régénéré par `make reference`.
- `knock/use_cases/` : chargeur collecteur (`loader.py`) et use case `lint`. Réutilisation pure de `resolve_imports`, `resolve_registry`, `resolve_ca_certs`, `resolve_mirror` et de la détection de collisions. Aucun port ni adaptateur nouveau.
- `docs/reference/schemas/` : nouveau schéma du rapport de lint, généré depuis le modèle Pydantic.
- Consommateurs : la CI du dépôt de politiques. `docs/policies/` (dossier `docs`) pourra s'y valider. `uske` n'est pas touché.

## Passes de cadrage

- Cadrage, passe 1 sur 5 (pendant l'exploration) : l'appelant est la CI du dépôt de politiques ; la profondeur est N1+N2, plus N3 si une configuration est présente ; la sortie donne toutes les erreurs, en JSON.
- Cadrage, passe 2 sur 5 : approche A (use case dédié, chargeur collecteur) ; nom `knock lint` ; N3 implicite avec saut tracé ; collisions possibles en avertissement.
