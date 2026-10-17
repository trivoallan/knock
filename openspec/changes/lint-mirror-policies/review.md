# Review

Revue due pour une raison : le livrable est une surface exposée à un tiers, un verbe CLI et un contrat JSON consommés par la CI du dépôt de politiques. Elle porte sur `proposal.md`, `specs/policy-lint/spec.md` et `design.md`.

## Grilles retenues

- **DevEx** : le livrable se consomme. Une personne l'appelle depuis une CI, lit sa sortie et l'exploite par machine.
- **Contrôle** : le livrable refuse. Son exit 1 bloque un merge. Il faut donc examiner ce qu'il laisse passer à tort, autant que ce qu'il bloque à tort.
- Pas de revue d'ingénierie : aucune décision n'est `irréversible` (le verbe est additif et se retire, D1 garde le comportement de `reconcile`), et le plan tient dans une MR.
- `/plan-devex-review` n'a pas été lancée. Les grilles ont été appliquées à la main, sur les artefacts.

## Findings et traitement

| # | Grille · dimension | Finding | Sévérité | Traitement |
| --- | --- | --- | --- | --- |
| 1 | Contrôle · faux passage | Un chemin mal orthographié ou un répertoire sans politique passe en vert : `rglob` sur un chemin absent rend une liste vide, et zéro politique ne donne aucune erreur. Une CI mal configurée validerait donc tout, indéfiniment. | Haute | **Corrigé dans la spec** : nouvelle exigence. Un chemin absent ou qui n'est pas un répertoire donne exit 3, et un arbre sans aucun fichier de politique donne une erreur, donc exit 1. |
| 2 | Contrôle · faux passage | `reconcile` présente le même défaut : un répertoire vide ne fait rien, sans le signaler. | Moyenne | Hors périmètre, car ça modifie le comportement de `reconcile` que D1 promet de garder. Consigné dans *Questions ouvertes* de `design.md`. |
| 3 | Contrôle · lisibilité du saut | Une CI sans `KNOCK_REGISTRIES` passe en vert sans N3. Le saut est dans `skipped`, mais un lecteur pressé peut le manquer. | Basse | **Corrigé dans la spec** : en texte, la sortie annonce les niveaux sautés sur une ligne en tête. |
| 4 | DevEx · exploitabilité | `loc` est un chemin de champs (`spec.imports[2].tags`), pas une ligne. Les annotations de MR (GitLab Code Quality, GitHub annotations) attendent un numéro de ligne, et `yaml.safe_load` le perd. | Moyenne | Accepté comme limite de la v1, car obtenir les lignes demande un autre chargeur YAML (marques de nœuds), donc une décision à part. Consigné dans *Questions ouvertes*. |
| 5 | DevEx · découvrabilité | Le JSON n'apparaît que sous `KNOCK_LOG_FORMAT=json` (D6). Un intégrateur qui lance `knock lint` voit du texte et peut croire qu'il n'y a pas de sortie machine. | Basse | `--help` et la référence CLI nomment la variable, avec un exemple d'appel CI. Une tâche s'en chargera. |
| 6 | DevEx · piège d'usage | `knock lint .` à la racine du dépôt de politiques lit aussi `.github/workflows/*.yml` ou `.gitlab-ci.yml` comme des politiques, et rapporte des erreurs absurdes. `reconcile` ferait de même. | Moyenne | On garde le comportement de `reconcile` : diverger casserait la garantie « même verdict » de D1. La référence CLI dit de pointer le répertoire des politiques, et le cas est repris dans la question ouverte n° 2. |
| 7 | Contrôle · angle mort | Deux politiques peuvent porter le même `metadata.name`. Ce nom estampille la provenance (`io.knock.policy`) et sert de clé au journal d'`uske`. Ni `reconcile` ni le lint prévu ne le détectent. | Moyenne | Hors périmètre : en faire une erreur rendrait lint plus strict que `reconcile`. Consigné dans *Questions ouvertes*, comme candidat à une change qui l'impose aux deux. |
| 8 | DevEx · testabilité de la spec | Le scénario « Same verdict as reconcile » passe par `reconcile --dry-run`, qui demande configuration et registres. Ce n'est pas exécutable hors ligne. | Basse | **Corrigé dans la spec** : le scénario porte sur le chargement de `reconcile` (`load_policy_dir`), le même chemin (D1). |

Finding trouvé pendant le découpage en tâches, à la lecture du code :

| # | Grille · dimension | Finding | Sévérité | Traitement |
| --- | --- | --- | --- | --- |
| 9 | Contrôle · faux passage | Le nom et les paramètres d'une étape `transform`/`remediate` ne sont vérifiés qu'au plan de `reconcile`. Un `injectCa` mal orthographié passerait N1 et N2 tels que la spec les décrivait. | Haute | **Corrigé** : spec (N2, scénario « Unknown or ill-formed transform step ») et `design.md` D9. |

## Critère d'achèvement

La revue est close quand trois conditions sont remplies :

- les findings 1, 3 et 8 sont reflétés dans `specs/policy-lint/spec.md` ;
- les findings 2, 4, 6 et 7 figurent dans *Questions ouvertes* de `design.md` ;
- la référence CLI (finding 5 et la consigne de pointage du finding 6) fait l'objet d'une tâche dans `tasks.md`.

Aucun finding n'est laissé sans traitement.
