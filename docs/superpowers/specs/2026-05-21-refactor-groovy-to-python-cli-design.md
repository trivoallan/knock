# Refactor Hub2Hub : Groovy Jenkins Shared Library → CLI Python

**Date** : 2026-05-21
**Statut** : Design validé, en attente de plan d'implémentation
**Branche cible** : `feat/python-cli`

## 1. Contexte et motivation

Le projet `shared-libs` héberge aujourd'hui la pipeline Hub2Hub : une Jenkins Shared Library Groovy (~2 340 lignes), complétée par quelques utilitaires Python (`ci/`, ~200 lignes) et une configuration GitLab CI. Le fichier `vars/importProduct.groovy` concentre 1 804 lignes et 12 fonctions ; la logique métier (semver, filtrage des tags, gestion EOL, archivage, génération de Dockerfile, notifications) est imbriquée avec les appels d'orchestration Jenkins.

Le refactor vise à extraire ce code métier dans un **CLI Python multi-environnement**, appelable indifféremment depuis Jenkins, GitLab CI ou un poste de développement.

Quatre moteurs cumulés :

- **Testabilité** : permettre les tests unitaires (pytest) ; aujourd'hui la seule validation est le dry-run Jenkins.
- **Maintenabilité** : sortir de Groovy/CPS ; éclater le monolithe `importProduct.groovy`.
- **Découplage de Jenkins** : préparer une sortie progressive de Jenkins (GitLab CI seul, ou exécution locale).
- **Onboarding / écosystème** : plus de devs maîtrisent Python ; outillage (linters, types, debug) plus mature.

## 2. Décisions structurantes

| Axe | Décision |
|---|---|
| Cible d'exécution | **Multi-environnement de première classe** : Jenkins, GitLab CI et local exécutent les mêmes commandes, sans spécificité d'orchestrateur dans le CLI |
| Forme du CLI | **Sous-commandes hiérarchiques par ressource** (style AWS CLI) |
| Stratégie de migration | **Big bang** (branche dédiée, refonte intégrale, switch en une fois) |
| Stratégie de tests | **Unitaires + intégration mockés**, coverage > 80 %, fixtures captures de production |
| Packaging | **Image OCI exécutable** publiée sur Harbor |
| Configuration / secrets | **12-factor** : env vars uniquement, aucune logique Vault dans le CLI |
| Périmètre | Shim Groovy minimal + `ci/` absorbé + `.gitlab-ci.yml` refondu + `resources/` réorganisés autour de Jinja2 |
| Localisation du code | **Même repo** `shared-libs` (un cycle de release) |

## 3. Surface du CLI

Nom : `h2h`. Image OCI : `registry-docker.apps.eul.sncf.fr/<projet-harbor-équipe>/h2h-cli:vX.Y.Z`. Framework : Typer.

```
h2h product import     [--dry-run-tags] [--dry-run-deletions] [--project] [--repository]
h2h product init       [--from-properties PATH]
h2h product delete     [--soft|--hard]
h2h proxycache update
h2h proxycache list
h2h archive restore    --tag --date
h2h archive purge      [--keep N] [--older-than DAYS]
h2h harbor health
h2h version
```

Un sous-groupe interne `h2h dev …` (non documenté pour les utilisateurs finaux, présent dans la même CLI) regroupe l'outillage de développement : `h2h dev capture` (cf. §8.3) pour capturer des fixtures depuis la production.

Toutes les sous-commandes :

- lisent leur configuration dans l'environnement (12-factor) ;
- acceptent `--log-format=json|text` et `--log-level=DEBUG|INFO|WARN|ERROR` ;
- retournent un code de sortie distinct par classe d'erreur (cf. §6) ;
- en mode `--dry-run-*` n'effectuent aucune écriture (Harbor, git push, Teams).

Le contexte (projet Harbor, repository, tag) est lu soit dans l'environnement (`H2H_PROJECT`, `H2H_REPOSITORY`), soit via flags explicites qui ont priorité.

## 4. Architecture interne (hexagonale)

```
hub2hub/                          # package Python
├── domain/                       # logique pure, aucun I/O
│   ├── semver.py                 # remplace sortBySemver/sortBySemverbyField
│   ├── properties.py             # parsing/validation properties.yml (Pydantic)
│   ├── tag_filter.py             # logique de retrieveTagsToImport (exclusions, regex, délai 7 j)
│   ├── eol.py                    # parseMarkdownTable + logique fetchEolDetails
│   ├── purge.py                  # purgeArchives (calcul des tags à supprimer)
│   ├── plan.py                   # plan d'import (pré-exécution)
│   └── labels.py                 # construction des labels fr.sncf.h2h.*
│
├── ports/                        # protocoles abstraits (typing.Protocol)
│   ├── harbor.py
│   ├── source_registry.py
│   ├── image_builder.py
│   ├── git_repo.py
│   ├── gitlab.py
│   ├── notifier.py
│   ├── eol_source.py
│   └── clock.py
│
├── adapters/                     # implémentations concrètes (I/O)
│   ├── harbor_http.py            # HarborApi en Python
│   ├── skopeo_cli.py             # wrapper subprocess skopeo
│   ├── buildkit_cli.py           # wrapper subprocess buildctl
│   ├── git_cli.py
│   ├── gitlab_http.py
│   ├── teams_webhook.py
│   ├── endoflife_http.py
│   └── system_clock.py
│
├── use_cases/                    # orchestre domain + ports
│   ├── product_import.py         # remplace importProduct() + processTag()
│   ├── product_init.py
│   ├── product_delete.py
│   ├── proxycache_update.py
│   ├── archive_restore.py
│   └── archive_purge.py
│
├── cli/                          # façade Typer (mince)
│   ├── main.py
│   ├── product.py
│   ├── proxycache.py
│   ├── archive.py
│   └── _di.py                    # injection de dépendances
│
├── templates/                    # Jinja2
│   ├── Dockerfile.j2
│   ├── properties.yml.j2
│   └── teams_notification.json.j2
│
├── resources/                    # données statiques (non-Python)
│   ├── regis_playbooks.yml
│   ├── certificats/
│   └── sncf_repos/               # scripts shell embarqués (cf. §5.2)
│
├── config.py                     # Pydantic Settings (lecture env vars)
├── logging.py                    # structlog
└── errors.py                     # hiérarchie d'exceptions

tests/
├── unit/
├── integration/
├── fixtures/
└── fakes/                        # implémentations de test des ports
```

**Règles d'or**

1. `domain/` n'importe rien d'autre que `domain/` et la stdlib. Pas de `requests`, pas de `subprocess`.
2. `use_cases/` reçoit ses ports injectés par constructeur. Aucun import direct d'adaptateur.
3. `cli/` ne fait que : parser args → instancier les ports concrets (`_di.py`) → appeler le use case → mapper l'exception en exit code.
4. Une fonction Groovy = une fonction Python dans `domain/` ou un use case. Pas de fichier monolithique.

## 5. Migration des `resources/`

### 5.1 Templates

| Aujourd'hui | Demain |
|---|---|
| `resources/Dockerfile.template` (sections décommentées par Groovy) | `templates/Dockerfile.j2` (blocs `{% if needs_apt %}…{% endif %}`) |
| `resources/properties.yml.template` | `templates/properties.yml.j2` |
| `resources/teams_notification.json.template` | `templates/teams_notification.json.j2` |
| `resources/regis-playbooks.yml` | `resources/regis_playbooks.yml` (lu, jamais templaté) |
| `resources/certificats/*` | `resources/certificats/*` (copiés dans l'image OCI, accédés via `importlib.resources`) |

### 5.2 Scripts shell embarqués

Les `resources/*.sh` (`add_sncf_https_sources.sh`, `install_sncf_keyring.sh`, `set_timezone.sh`, `update_keystore.sh`, etc.) s'exécutent à l'intérieur de l'**image cliente** en cours de construction (Alpine/Debian/CentOS du produit importé), pas dans le CLI. Ils restent donc en **POSIX shell** :

- versionnés dans `hub2hub/resources/sncf_repos/` ;
- accédés via `importlib.resources` côté CLI ;
- injectés dans le Dockerfile généré par Jinja (instructions `COPY` depuis un répertoire d'assets) ;
- linté avec `shellcheck` en CI.

Ce qui devient du Python, c'est uniquement le code Groovy qui manipule ces scripts (lecture, sélection conditionnelle, paramétrage). Réécrire les scripts en Python est exclu : cela imposerait un runtime Python à toutes les images clientes.

## 6. Configuration, secrets, erreurs

### 6.1 Contrat de variables d'environnement (12-factor)

Lu par `hub2hub/config.py` (Pydantic Settings) au démarrage. Aucune lecture d'env vars en dehors de ce module.

```
# Harbor (cible)
H2H_HARBOR_URL
H2H_HARBOR_USER
H2H_HARBOR_PASSWORD                (secret)
H2H_HARBOR_PROJECT_DEFAULT         optionnel

# Harbor (miroir orange/EKS, optionnel)
H2H_HARBOR_ORANGE_URL
H2H_HARBOR_ORANGE_USER
H2H_HARBOR_ORANGE_PASSWORD         (secret)

# GitLab
H2H_GITLAB_URL
H2H_GITLAB_TOKEN                   (secret)
H2H_GITLAB_GROUP

# Teams
H2H_TEAMS_WEBHOOK_URL              (secret, optionnel — désactive la notification si absent)

# EOL
H2H_ENDOFLIFE_URL                  défaut https://endoflife.date/api

# Comportement
H2H_LOG_FORMAT                     json|text — défaut text
H2H_LOG_LEVEL                      défaut INFO
H2H_DRY_RUN_TAGS                   défaut false
H2H_DRY_RUN_DELETIONS              défaut false
H2H_WORK_DIR                       défaut /tmp/h2h-work

# Contexte (rempli par l'orchestrateur ou l'utilisateur)
H2H_PROJECT
H2H_REPOSITORY
```

Aucune variable `JENKINS_*` / `CI_*` / `GITLAB_CI_*` n'est lue. Chaque orchestrateur fait le mapping en amont.

### 6.2 Validation au démarrage

Pydantic Settings :

- vérifie la présence des champs requis selon la sous-commande ;
- échoue *fast* avec un message lisible et **exit 3** (erreur de configuration) ;
- masque les secrets dans les logs via `SecretStr`.

### 6.3 Hiérarchie d'erreurs et exit codes

```
H2HError                           (base)
├── DomainError          exit 1    erreur métier / validation
│   ├── PropertiesValidationError
│   ├── NoTagsToImportError
│   └── EolDateInconsistencyError
├── AdapterError         exit 2    erreur infra / dépendance externe
│   ├── HarborError
│   │   ├── HarborAuthError
│   │   ├── HarborNotFoundError
│   │   └── HarborTransientError   (retried 5× avant remontée)
│   ├── GitError
│   ├── SkopeoError
│   ├── BuildkitError
│   ├── GitLabError
│   └── EolSourceError
├── ConfigError          exit 3    config invalide / manquante
└── InternalError        exit 4    bug, assertion
```

**Retry** centralisé dans un décorateur `@retry_transient(max=5, backoff="expo")` appliqué dans les adaptateurs concernés. Aucun retry dans `domain/`. Remplace `retryCodeBlock` du Groovy.

**Logs JSON** (quand `--log-format=json`) : chaque ligne = un événement structuré (`level`, `event`, `project`, `repository`, `tag`, `duration_ms`, `error_class`…), ingestible Splunk/Loki sans regex.

## 7. Flux d'un `h2h product import`

```
CLI                              Use-case                          Domain
───                              ────────                          ──────
h2h product import
  │
  ├─ parse args + env ──────►  ProductImport(ctx)
  │                              │
  │                              ├─ git.clone(repo)               ─► (GitRepoPort)
  │                              ├─ load_properties(yml) ────────►   domain.properties.parse_and_validate()
  │                              ├─ all_src_tags = src.list() ───► (SourceRegistryPort)
  │                              ├─ filter ─────────────────────►   domain.tag_filter.compute_tags_to_import(
  │                              │                                    src_tags, properties, harbor_state, now)
  │                              │                                    → TagsToImport, TagsToUpdate, TagsToDelete
  │                              │
  │                              ├─ for tag in tags_to_import :
  │                              │   ├─ digest = src.digest(tag) ─► (SourceRegistryPort)
  │                              │   ├─ plan   = domain.plan.build(tag, properties, digest, eol_info)
  │                              │   ├─ dockerfile = render(Dockerfile.j2, plan)
  │                              │   ├─ builder.build_and_push(dockerfile) ─► (ImageBuilderPort)
  │                              │   ├─ harbor.add_labels(...)              ─► (HarborPort)
  │                              │   └─ git.commit_tag_artifacts(...)
  │                              │
  │                              ├─ for tag in tags_to_delete :
  │                              │   └─ harbor.delete_or_soft_label(...)
  │                              │
  │                              ├─ archive_purge.run(...)         (use case réutilisé)
  │                              ├─ git.commit_and_push_product_repo(...)
  │                              └─ notifier.send(teams_payload)   ─► (NotifierPort)
  │
  └─ map exception → exit code
```

**Idée clé** : `compute_tags_to_import` est une fonction pure (`(src_tags, properties, harbor_state, now) → TagsToImport`). C'est là que vit la logique métier compliquée (délai 7 jours, regex d'exclusion, semver, archivage). Testable avec des dizaines de fixtures sans aucune I/O.

## 8. Stratégie de tests

### 8.1 Trois niveaux

**Unitaires** (`tests/unit/`) — la majorité du volume.

- Cible : `domain/` (toutes fonctions pures) et `use_cases/` (orchestration avec ports fakés).
- Outils : `pytest`, `pytest-cov`, `hypothesis` pour les invariants (semver, filtres de tags).
- Pas de réseau, pas de subprocess, pas de filesystem hors `tmp_path`.
- Ports fakés via `Protocol` + petites classes `FakeHarbor`, `FakeGitRepo`, `FakeClock` dans `tests/fakes/`.
- **Cible coverage : > 90 % sur `domain/`, > 80 % global**.

**Intégration** (`tests/integration/`) — adaptateurs en isolation.

- HTTP : `respx` ou `responses` — appels Harbor/GitLab/Teams/EOL contre des fixtures de réponses réelles.
- CLI externes (`skopeo`, `buildctl`, `git`) : binaires mockés dans `tests/fake-bins/` en tête de `PATH` ; le test inspecte les arguments reçus.

**Snapshot / fixtures de production** (`tests/fixtures/`)

- Captures de `properties.yml` réels (anonymisés) couvrant les cas tordus.
- Pour chaque fixture : sortie attendue de `compute_tags_to_import`, du Dockerfile rendu, du payload Teams.
- Comparaison via `syrupy` (snapshot testing) — filet anti-régression de la cutover big bang.

### 8.2 Smoke E2E

Un scénario unique en CI : Harbor mocké HTTP exhaustif + GitLab mocké, exécution d'un `h2h product import` sur un produit factice (`busybox:1.36`), vérification des écritures attendues. Volontairement un seul, car coûteux à maintenir.

### 8.3 Capture de fixtures depuis la production

Avant la cutover, un outil interne `h2h dev capture --project X --repository Y` appelle la prod en read-only et sauvegarde les réponses Harbor, le `properties.yml`, les tags. Objectif : 10 à 20 fixtures couvrant produit simple, produit avec EOL, produit avec exclusions regex, produit archivable, produit à digest changeant, produit multi-tag.

Ces fixtures **bloquent** la fusion : tant que les snapshots ne sont pas verts sur les produits réels les plus critiques, pas de switch.

### 8.4 CI

Pipeline GitLab dédié sur `shared-libs` :

- `lint` : ruff, mypy strict sur `domain/` et `use_cases/`, shellcheck sur scripts shell.
- `test:unit` : pytest, coverage gate à 80 %.
- `test:integration` : respx + fake-bins.
- `test:smoke` : E2E containerisé.
- `build:image` : build de `h2h-cli:vX.Y.Z` (BuildKit).
- `publish:image` : push sur Harbor au tag git.

## 9. Packaging, image, shims

### 9.1 Outillage Python

- Gestionnaire de projet : `uv` (lockfile reproductible, retenu de manière ferme — pas d'`alternative`).
- Build backend : `hatchling`.
- Python : 3.12.
- Linters : `ruff` (lint + format), `mypy --strict` sur `domain/` et `use_cases/`.
- CLI : `typer`.
- HTTP : `httpx` + `tenacity` (retry).
- Templates : `jinja2`.
- Validation : `pydantic` v2.
- Logs : `structlog`.
- Tests : `pytest`, `respx`, `syrupy`, `hypothesis`, `pytest-cov`.

### 9.2 Image OCI

`Dockerfile` à la racine, multi-stage :

```dockerfile
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY hub2hub ./hub2hub
RUN pip install uv && uv build

FROM debian:12-slim
COPY --from=quay.io/skopeo/stable:v1.13 /usr/bin/skopeo /usr/bin/
COPY --from=moby/buildkit:v0.13-rootless /usr/bin/buildctl /usr/bin/
RUN apt-get update && apt-get install -y --no-install-recommends \
      git ca-certificates python3.12 python3-pip && \
    rm -rf /var/lib/apt/lists/*
COPY --from=build /src/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
ENTRYPOINT ["h2h"]
```

Image publiée sur Harbor : `registry-docker.apps.eul.sncf.fr/<projet-harbor-équipe>/h2h-cli:vX.Y.Z` (et `latest` sur master).

### 9.3 Shim Jenkins (`vars/`)

L'API publique (`importProduct()`, `initProduct()`, `deleteProduct()`) est **préservée** pour les Jenkinsfile clients existants, mais le corps devient trivial. Exemple `vars/importProduct.groovy` ramené de 1 804 à ~40 lignes :

```groovy
def call() {
    def envVars = [
        "H2H_PROJECT=${params.PROJECT}",
        "H2H_REPOSITORY=${params.REPOSITORY}",
        "H2H_DRY_RUN_TAGS=${params.DRY_RUN_TAGS ?: 'false'}",
    ]
    withCredentials([
        usernamePassword(credentialsId: 'HARBOR-PRODUCTION',
                         usernameVariable: 'H2H_HARBOR_USER',
                         passwordVariable: 'H2H_HARBOR_PASSWORD'),
        string(credentialsId: 'gitlab', variable: 'H2H_GITLAB_TOKEN'),
        string(credentialsId: 'teams-webhook', variable: 'H2H_TEAMS_WEBHOOK_URL'),
    ]) {
        withEnv(envVars) {
            sh "docker run --rm \
                -e H2H_PROJECT -e H2H_REPOSITORY \
                -e H2H_HARBOR_USER -e H2H_HARBOR_PASSWORD \
                -e H2H_GITLAB_TOKEN -e H2H_TEAMS_WEBHOOK_URL \
                -e H2H_DRY_RUN_TAGS \
                ${H2H_IMAGE} product import"
        }
    }
}
```

`HarborApi.groovy` est supprimé (plus de consommateur Groovy direct).

### 9.4 `.gitlab-ci.yml` refondu

```yaml
update-proxycaches:
  image: registry-docker.apps.eul.sncf.fr/<projet-harbor-équipe>/h2h-cli:latest
  script:
    - h2h proxycache update
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"

restore-archive:
  image: registry-docker.apps.eul.sncf.fr/<projet-harbor-équipe>/h2h-cli:latest
  script:
    - h2h archive restore --project "$PROJECT_NAME" --repository "$REPOSITORY_NAME" --tag "$TAG_NAME" --date "$DATE"
  when: manual
```

Les blocs `.install_glab`, `.auth_glab`, `.set_gitlab_variable` du `.gitlab-ci.yml` actuel disparaissent : la résolution Vault → env vars passe par un `before_script` partagé ; `glab` n'est plus utilisé (l'API REST GitLab est appelée par le CLI quand strictement nécessaire).

## 10. Séquençage du big bang

```
J+0   Spec validé, plan d'implémentation rédigé
J+0   Branche feat/python-cli créée

Phase A — fondations (≈ 1 sprint)
  · pyproject.toml, layout, CI pytest, lint, image vide
  · outil h2h dev capture + collecte ~20 fixtures de prod
  · domain/ complet + tests > 90 % (semver, properties, tag_filter, eol, purge, plan, labels)

Phase B — adapters (≈ 1 sprint)
  · tous les ports + adapters avec tests d'intégration mockés
  · image Docker buildée en CI, publiée en tag v0-rc

Phase C — use cases (1 à 2 sprints)
  · product_init, product_delete, proxycache_update, archive_restore, archive_purge
  · product_import en dernier (le gros morceau)
  · snapshot tests verts sur toutes les fixtures

Phase D — cutover (≈ 1 sprint)
  · shims Jenkins en branche, dry-run forcé sur tous les produits actifs
  · diff manuel logs Groovy vs logs Python sur un échantillon
  · merge sur master ; suppression de l'ancien code Groovy
  · freeze 1 semaine d'observation rapprochée, rollback prêt (revert merge)

Phase E — décommission
  · suppression définitive de ci/, du HarborApi.groovy, du corps métier dans vars/
  · doc d'onboarding mise à jour
```

Durée prévisionnelle : **4 à 6 sprints**. Le risque principal est `processTag` (~650 lignes Groovy) — à isoler tôt en sous-fonctions pendant la lecture du Groovy.

## 11. Critères d'acceptation pour la cutover

La fusion sur `master` exige :

- coverage global > 80 % (domain > 90 %) ;
- 100 % des fixtures de production capturées passent les snapshot tests ;
- pour les 5 produits Hub2Hub les plus actifs : diff manuel approuvé entre une exécution dry-run du nouveau CLI et une exécution dry-run du Groovy actuel, sur les mêmes inputs ;
- image OCI buildée, signée et publiée sur Harbor en `latest` ;
- runbook de rollback rédigé (revert du merge + republication d'une image `h2h-cli:rollback`).

## 12. Hors-périmètre explicite

- Migration vers GitLab CI sans Jenkins : le shim Jenkins est conservé en sortie de refactor. Le décommissionnement de Jenkins est un projet ultérieur facilité par ce refactor.
- Refonte du protocole Hub2Hub ou du contenu des `properties.yml` clients : iso-fonctionnel.
- Réécriture des scripts shell embarqués des images clientes : ils restent POSIX shell.
- Migration vers une autre registry que Harbor.
