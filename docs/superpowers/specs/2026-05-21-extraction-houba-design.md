# Extraction du CLI Python dans le repo `houba`

**Date** : 2026-05-21
**Statut** : Design validé, en attente de plan d'implémentation
**Base d'extraction** : `shared-libs@v0.1.0-phase-a` (commit `096703a` + post-bilan)

## 1. Contexte

Le brainstorming initial (cf. [2026-05-21-refactor-groovy-to-python-cli-design.md](2026-05-21-refactor-groovy-to-python-cli-design.md), question 9) avait retenu de garder le code Python dans le repo `shared-libs`. Phase A est désormais livrée (91 tests verts, coverage 94.5 %, image OCI fonctionnelle) et le CLI est structurellement autonome du Groovy de la Jenkins Shared Library.

L'utilisateur souhaite maintenant inverser cette décision : extraire le code Python dans un repo dédié et le renommer `houba`. Le nom du projet métier (la pipeline Hub2Hub) reste inchangé ; seul l'outillage Python prend un nom propre.

## 2. Décisions structurantes

| Axe | Décision |
|---|---|
| Portée du renommage | **houba = CLI uniquement** — le projet métier reste Hub2Hub |
| Variables d'environnement | `H2H_*` → **`HOUBA_*`** |
| Labels OCI | **`fr.sncf.h2h.*` conservés** (compat `deleteProduct.groovy`) |
| Historique git | **`git filter-repo`** (préservation des ~35 commits TDD de Phase A) |
| Nettoyage `shared-libs` | **Agressif** (suppression `hub2hub/`, `tests/`, `pyproject.toml`, `Dockerfile`, `resources/`, jobs `python:*` du `.gitlab-ci.yml`) |
| `resources/` | **Déplacées dans `houba/houba/resources/`** (single source of truth) |
| Stratégie d'exécution | **Big bang séquentiel** (pas de cohabitation) |
| Timing | **Maintenant**, avant tout démarrage Phase B |

## 3. Cible des deux repos après extraction

### Repo `houba` (nouveau)

```
houba/
├── pyproject.toml                    name = "houba"  ;  scripts.houba = "houba.cli.main:app"
├── uv.lock
├── .python-version
├── .gitignore
├── Dockerfile                        image houba:vX.Y.Z
├── .dockerignore
├── .gitlab-ci.yml                    jobs Python seuls : lint + test + build:image + publish:image
├── README.md                         pointe vers shared-libs pour le projet métier
│
├── houba/                            ex-hub2hub/
│   ├── errors.py, config.py, logging.py
│   ├── ports/, adapters/, domain/, cli/
│   └── resources/                    NOUVEL emplacement
│       ├── sncf_repos/               scripts shell SNCF
│       ├── certificats/
│       └── templates/                Dockerfile.template, properties.yml.template
│
├── tests/                            renommée hub2hub → houba dans les imports
│   ├── fakes/, fixtures/, fake-bins/
│   ├── unit/
│   └── integration/
│
└── docs/superpowers/
    ├── specs/2026-05-21-refactor-groovy-to-python-cli-design.md
    ├── specs/2026-05-21-extraction-houba-design.md
    ├── plans/2026-05-21-phase-a-fondations-domain.md
    └── runbooks/capture-fixtures.md
```

### Repo `shared-libs` (après nettoyage)

```
shared-libs/
├── vars/                             Groovy Jenkins Shared Library (inchangée)
├── ci/                               legacy Python (sera supprimé en Phase B-C de houba)
├── .gitlab-ci.yml                    jobs Groovy + restore-archive (sans les python:*)
├── .groovylintrc.json
├── .gitignore
└── README.md                         section "L'outil Python vit dans le repo houba (<url>)"
```

**Tags de jonction** : `shared-libs@pre-houba-extract` (sur le commit du HEAD Phase A) ↔ `houba@v0.1.0-phase-a` (sur le HEAD post-rename équivalent).

## 4. Règles de renommage mécanique

### Substitutions textuelles

| Avant | Après | Périmètre |
|---|---|---|
| `hub2hub` | `houba` | Tous fichiers SAUF `docs/superpowers/specs/` et `docs/superpowers/plans/` (références historiques) |
| `H2H_` (préfixe env var) | `HOUBA_` | `config.py`, tests, Dockerfile, `.gitlab-ci.yml` |
| `h2h` (mot entier, binary CLI) | `houba` | `[project.scripts]`, docstrings, CLI help |
| `h2h-cli` | `houba` | Dockerfile, `.gitlab-ci.yml`, runbook |

### Substitutions exclues

| Pattern | Raison |
|---|---|
| `fr.sncf.h2h.*` | Labels OCI = projet métier Hub2Hub |
| `Hub2Hub` (mentions dans docs/specs) | Le projet s'appelle toujours Hub2Hub |
| `04228.proxy.docker.io` et noms projets Harbor | Configuration métier |

### Renommages de chemin

| Avant | Après |
|---|---|
| `hub2hub/` (répertoire package) | `houba/` |
| `resources/` (à la racine de shared-libs) | `houba/houba/resources/` |
| `tests/fixtures/synthetic/*.yml` et `.md` | identiques (contenu non modifié) |

## 5. Workflow d'extraction (big bang séquentiel)

### Pré-requis

- `git-filter-repo` installé (`brew install git-filter-repo` ou `pip install --user git-filter-repo`)
- Droits de création de repo sur le GitLab SNCF
- Phase A poussée sur `shared-libs/origin`

### Étapes

```
J+0  Préparation
─────────────────
1. Depuis le repo principal `shared-libs` (PAS depuis le worktree, qui retient
   actuellement la branche `tritri/mystifying-montalcini-2ee38b`) :
   git checkout master          # ou la branche d'intégration cible (main, develop, etc.)
   git merge --ff-only tritri/mystifying-montalcini-2ee38b
   # → master avance jusqu'au HEAD post-Phase A (commit 096703a + post-bilan)
   git tag pre-houba-extract
   git tag v0.1.0-phase-a       # si pas déjà posé localement
   git push origin master pre-houba-extract v0.1.0-phase-a

2. Clone de travail temporaire :
   cd ~/h2h-split/
   git clone --no-local <shared-libs-url> houba-extract
   cd houba-extract
   git checkout pre-houba-extract -b extract

J+0  Extraction (filter-repo)
─────────────────
3. git filter-repo \
       --path pyproject.toml \
       --path uv.lock \
       --path .python-version \
       --path .gitignore \
       --path .dockerignore \
       --path Dockerfile \
       --path hub2hub/ \
       --path tests/ \
       --path resources/ \
       --path docs/superpowers/specs/ \
       --path docs/superpowers/plans/ \
       --path docs/superpowers/runbooks/

J+0  Renommage répertoire
─────────────────
4. git mv hub2hub houba
   git mv resources houba/resources
   git commit -m "chore(rename): hub2hub → houba (package + resources)"

J+0  Renommage textuel (sed + commit dédié)
─────────────────
5. # Ordre critique :
   # Sed 1 : H2H_ → HOUBA_  (hors docs/superpowers/specs/ et plans/)
   # Sed 2 : hub2hub → houba (mots entiers)
   # Sed 3 : h2h-cli → houba (IMAGE NAME, AVANT sed 4 sinon sed 4 produit "houba-cli")
   # Sed 4 : \bh2h\b → houba (mot entier, exclut fr.sncf.h2h.* via Perl lookbehind/lookahead)
   git add -A
   git commit -m "chore(rename): h2h/H2H_ → houba/HOUBA_ (paths textuels)"

J+0  Vérifications
─────────────────
6. uv sync
   uv run pytest -v                       91 tests verts
   uv run mypy houba                      clean
   uv run ruff check . && uv run ruff format --check .
   docker build -t houba:phase-a .
   docker run --rm houba:phase-a version  affiche 0.1.0.dev0
   grep -rn '\bhub2hub\b\|\bH2H_' houba tests pyproject.toml Dockerfile .gitlab-ci.yml \
       | grep -v docs/superpowers/specs | grep -v docs/superpowers/plans
   Aucun match attendu hors specs/plans

J+0  .gitlab-ci.yml dédié
─────────────────
7. Réécriture pour ne contenir QUE les jobs Python.
   Suppression de auth_glab, set_gitlab_variable, restore-archive, etc.
   git commit -m "ci: nouveau .gitlab-ci.yml dédié à houba"

J+0  Tag + Push
─────────────────
8. git tag v0.1.0-phase-a
   git remote rename origin shared-libs-source
   git remote add origin <houba-url>
   git push -u origin extract:master
   git push origin v0.1.0-phase-a

J+1  Nettoyage shared-libs
─────────────────
9. Sur shared-libs, branche depuis HEAD Phase A :
   git checkout -b chore/post-houba-cleanup
   git rm -r hub2hub/ tests/ resources/ docs/superpowers/
   git rm pyproject.toml uv.lock .python-version Dockerfile .dockerignore
   Édition manuelle de .gitlab-ci.yml : retrait des jobs python:*
   Édition README.md : mention houba
   git commit -m "chore: extraction du Python vers le repo houba (cf. pre-houba-extract)"
   Push + MR
```

### Estimation wall-clock

- Étapes 1-8 : 30-60 min
- Étapes 9-10 : 15 min + revue MR

## 6. Critères de done

### Côté `houba`

- Repo créé, branche `master` reçue, tag `v0.1.0-phase-a`
- `git log --oneline | wc -l` ≥ 30 (historique préservé)
- `uv sync` réussit
- `uv run pytest -v` : 91 tests verts
- Coverage global > 80 %, `houba.domain` > 90 %
- `uv run mypy houba` clean
- `uv run ruff check . && uv run ruff format --check .` clean
- `docker build -t houba:phase-a .` réussit
- `docker run --rm houba:phase-a version` affiche `0.1.0.dev0`
- `docker run --rm houba:phase-a --help` liste `version` et `dev`
- `grep -rn '\bhub2hub\b' houba/ tests/ pyproject.toml Dockerfile .gitlab-ci.yml` : zéro match
- `grep -rn '\bH2H_' houba/ tests/ pyproject.toml Dockerfile .gitlab-ci.yml` : zéro match
- `grep -rn 'fr.sncf.h2h' houba/ tests/` : matchs préservés (labels OCI)
- Pipeline CI vert sur `master`

### Côté `shared-libs`

- Tag `pre-houba-extract` poussé sur `origin`
- Branche `chore/post-houba-cleanup` créée et mergée
- Plus aucun fichier Python ; `.gitlab-ci.yml` débarrassé des jobs `python:*`
- README pointe vers `houba`
- Pipeline CI vert après cleanup

## 7. Plan de rollback

| Stade | Stratégie |
|---|---|
| **Houba pas encore pushé** | Supprimer le clone de travail. Aucun impact externe. |
| **Houba pushé, shared-libs pas encore nettoyé** | Archive le repo houba sur GitLab. Reprise possible en monorepo. ~10 min. |
| **Les deux poussés et mergés** | Revert la MR `chore/post-houba-cleanup`. Archive `houba`. Re-pousser les éventuels commits Phase B vers shared-libs. ~30 min + revue MR. |

### Critères déclencheurs de rollback

- Régression de tests entre `shared-libs@v0.1.0-phase-a` et `houba@v0.1.0-phase-a`
- `mypy` ou `ruff` red sur `houba` sans cause technique identifiable
- `docker run houba:phase-a version` ne fonctionne pas
- Conflit organisationnel (GitLab SNCF refuse la création, équipe pas prête)

## 8. Smoke tests post-bascule

```bash
# Smoke 1 — env vars HOUBA_*
HOUBA_HARBOR_URL=https://test HOUBA_HARBOR_USER=u HOUBA_HARBOR_PASSWORD=p \
HOUBA_GITLAB_URL=https://gl HOUBA_GITLAB_TOKEN=t HOUBA_GITLAB_GROUP=g \
uv run houba version
# → 0.1.0.dev0

# Smoke 2 — labels OCI préservés
uv run python -c "
from datetime import UTC, datetime
from houba.domain.labels import build_labels
labels = build_labels(
    src_registry='docker.io', src_repository='r', src_tag='v1', src_digest='sha256:x',
    import_date=datetime(2026,5,21,tzinfo=UTC), harbor='blue',
    eol_product=None, eol_date=None,
)
assert 'fr.sncf.h2h.source.registry' in labels
print('OK labels conservés')
"

# Smoke 3 — image OCI complète
docker build -t houba:smoke .
docker run --rm houba:smoke version
docker run --rm houba:smoke --help
docker run --rm houba:smoke dev --help
docker run --rm houba:smoke dev capture --help
```

## 9. Coordination cross-repo

| Élément | `shared-libs` | `houba` |
|---|---|---|
| Tag d'origine | `pre-houba-extract` | `v0.1.0-phase-a` |
| README | section vers houba | section vers shared-libs (projet Hub2Hub) |
| Specs Phase A | supprimés (déplacés vers houba via filter-repo) | présents sous `docs/superpowers/specs/` |
| Issues | issues Python migrent vers tracker houba | nouvelles issues "outil" ici |
| Releases | plus aucune release Python | tags `v0.X.Y` indépendants |

## 10. Hors-périmètre explicite

- **Phase B** (adapters write, use cases) : démarre dans `houba` après l'extraction. Brainstorming + plan séparés.
- **Migration des `*.groovy` vers des shims minimaux** : reste dans `shared-libs`, scope Phase D du plan original.
- **Décommission de `ci/restore-archive.py`** et autres scripts Python legacy de `shared-libs` : déjà prévu Phase B-E du plan original (absorbés dans houba comme sous-commandes).
- **Renommage des labels OCI `fr.sncf.h2h.*`** : explicitement refusé (compat `deleteProduct.groovy`).

## 11. Référence

- Spec initial : [2026-05-21-refactor-groovy-to-python-cli-design.md](2026-05-21-refactor-groovy-to-python-cli-design.md)
- Plan Phase A : [../plans/2026-05-21-phase-a-fondations-domain.md](../plans/2026-05-21-phase-a-fondations-domain.md)
- Tag de départ : `shared-libs@v0.1.0-phase-a` (commit `096703a` + post-bilan)
