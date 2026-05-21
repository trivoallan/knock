# Extraction du CLI Python dans le repo `houba` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extraire le code Python actuellement dans `shared-libs/` (Phase A, ~35 commits, 91 tests) vers un nouveau repo dédié `houba`, en préservant l'historique via `git filter-repo` et en renommant `hub2hub`/`h2h`/`H2H_*` vers `houba`/`HOUBA_*`.

**Architecture :** Big bang séquentiel. Une seule fenêtre de bascule : push de Phase A sur `shared-libs/origin` (avec tag d'extraction), extraction filter-repo + renames mécaniques dans un clone temporaire, push vers le repo `houba` neuf, puis cleanup agressif de `shared-libs` sur une branche dédiée. Aucune cohabitation prolongée.

**Tech Stack :** `git` 2.x, `git-filter-repo` (homebrew ou pip), `sed`/`perl` POSIX, `uv` 0.x, Python 3.12, Docker.

**Référence spec :** [docs/superpowers/specs/2026-05-21-extraction-houba-design.md](../specs/2026-05-21-extraction-houba-design.md)

---

## Préambule — État de départ

- Travail effectué dans un worktree `shared-libs/.claude/worktrees/mystifying-montalcini-2ee38b/` sur la branche `tritri/mystifying-montalcini-2ee38b`.
- HEAD de cette branche : commits Phase A jusqu'au tag local `v0.1.0-phase-a` plus les commits du bilan extraction houba (`558a9ec` runbook, `9375c54` spec extraction, etc.).
- L'`origin` distant `shared-libs` ne connaît pas encore Phase A : tous les commits sont locaux.
- 91 tests verts, mypy strict + ruff clean, image Docker `h2h-cli:phase-a` build OK.

---

## Carte des artefacts produits

| Artefact | Type | Localisation |
|---|---|---|
| Tag `pre-houba-extract` | annotated tag | `shared-libs@origin` |
| Tag `v0.1.0-phase-a` | annotated tag | `shared-libs@origin` et `houba@origin` |
| Repo `houba` (master) | nouveau repo GitLab SNCF | `<houba-url-à-renseigner>` |
| Branche `chore/post-houba-cleanup` | branche shared-libs | `shared-libs@origin` |

Aucun fichier source `*.py` n'est créé par ce plan — uniquement renommé, déplacé, ou supprimé.

---

## Task 1 : Vérifier les pré-requis outillage

**Files :** Aucune modification.

- [ ] **Step 1 : Vérifier `git-filter-repo`**

```bash
git filter-repo --version
```

Expected : affiche une version (≥ 2.38).

Si absent :

```bash
brew install git-filter-repo                 # macOS
# OU
pip install --user git-filter-repo           # Linux/Windows
```

- [ ] **Step 2 : Vérifier `uv`, `python`, `docker`**

```bash
uv --version
python3.12 --version
docker --version
git --version
```

Expected : `uv` ≥ 0.4, Python 3.12.x, Docker ≥ 24, git ≥ 2.30.

- [ ] **Step 3 : Vérifier que le repo principal `shared-libs` connaît la branche du worktree**

Depuis le répertoire principal du repo `shared-libs` (PAS le worktree) :

```bash
cd /Users/tristan/Documents/Workspaces/ttc/shared-libs
git branch --list 'tritri/mystifying-montalcini-2ee38b'
git log --oneline tritri/mystifying-montalcini-2ee38b -5
```

Expected : la branche existe et son log montre les commits Phase A récents (`9375c54`, `096703a`…).

---

## Task 2 : Pousser Phase A sur `shared-libs/origin`

**Files :** Aucune modification de fichier source.

- [ ] **Step 1 : Identifier la branche cible**

Depuis le repo principal `shared-libs` :

```bash
git branch -r | head -5     # identifie origin/master, origin/main, etc.
```

Notez le nom exact de la branche d'intégration (`master` ou `main` selon convention SNCF). Le reste du plan suppose `master`. Adapter si nécessaire.

- [ ] **Step 2 : Fast-forward `master` vers le HEAD de Phase A**

```bash
cd /Users/tristan/Documents/Workspaces/ttc/shared-libs
git checkout master
git pull --ff-only origin master                 # à jour avec origin
git merge --ff-only tritri/mystifying-montalcini-2ee38b
```

Expected : `Updating <old>..9375c54` (ou le HEAD courant de la branche), `Fast-forward`. Pas de conflit.

Si la fast-forward n'est pas possible (master a avancé en parallèle), STOP — résoudre en escalade (rebase ou MR classique avant extraction).

- [ ] **Step 3 : Poser les tags**

```bash
git tag -a pre-houba-extract -m "Point d'extraction du code Python vers le repo houba — cf. docs/superpowers/specs/2026-05-21-extraction-houba-design.md"
git tag -a v0.1.0-phase-a -m "Phase A — fondations + couche domain/" 2>/dev/null || echo "tag v0.1.0-phase-a déjà existant"
```

Expected : tag créé (ou message indiquant qu'il existe déjà localement).

- [ ] **Step 4 : Push branche + tags**

```bash
git push origin master pre-houba-extract v0.1.0-phase-a
```

Expected : tous les refs poussés, pas d'erreur.

- [ ] **Step 5 : Vérification**

```bash
git ls-remote --tags origin | grep -E 'pre-houba-extract|v0.1.0-phase-a'
git ls-remote --heads origin | grep master
```

Expected : 2 tags + 1 branche présents côté distant.

---

## Task 3 : Cloner le repo de travail temporaire et exécuter `filter-repo`

**Files :** Création du clone dans `~/h2h-split/houba-extract/`.

- [ ] **Step 1 : Préparer le répertoire temporaire**

```bash
mkdir -p ~/h2h-split
cd ~/h2h-split
rm -rf houba-extract       # repart d'une base propre si une tentative précédente a échoué
```

- [ ] **Step 2 : Cloner avec `--no-local`**

```bash
git clone --no-local <shared-libs-url> houba-extract
```

Note : remplacer `<shared-libs-url>` par l'URL réelle (HTTPS ou SSH). `--no-local` force une vraie copie même si le source est sur le même disque — évite les liens durs qui rendraient `filter-repo` dangereux.

Expected : clone réussi, `houba-extract/` créé.

- [ ] **Step 3 : Se positionner sur le tag d'extraction**

```bash
cd ~/h2h-split/houba-extract
git checkout pre-houba-extract -b extract
git log --oneline -5
```

Expected : HEAD = `pre-houba-extract`, branche locale `extract` créée.

- [ ] **Step 4 : Lancer `git filter-repo`**

```bash
git filter-repo \
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
```

Expected : output indique les commits réécrits, durée < 10 s pour ~35 commits.

- [ ] **Step 5 : Vérifier l'historique et le contenu**

```bash
git log --oneline | wc -l            # ≥ 30 commits préservés
ls -la                                # racine du repo
ls hub2hub/                           # contenu du package
ls tests/                             # tests + fakes + fixtures + fake-bins
ls resources/                         # Dockerfile.template, *.sh, certificats/
```

Expected :
- Au moins 30 commits dans l'historique
- Présence de `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `.dockerignore`, `Dockerfile`, `hub2hub/`, `tests/`, `resources/`, `docs/superpowers/`
- ABSENCE de `vars/`, `ci/`, `.gitlab-ci.yml`, `.groovylintrc.json`, `resources/regis-playbooks.yml` (wait — `regis-playbooks.yml` est dans `resources/`, donc inclus — vérifier qu'il y est si on veut le garder, sinon le supprimer plus tard)

`filter-repo` supprime automatiquement le remote `origin` pour éviter un push accidentel sur le repo source.

---

## Task 4 : Renommer le répertoire `hub2hub/` → `houba/` et déplacer `resources/`

**Files :**
- Renommer : `hub2hub/` → `houba/`
- Déplacer : `resources/` → `houba/resources/`

- [ ] **Step 1 : Renommer le package**

```bash
cd ~/h2h-split/houba-extract
git mv hub2hub houba
```

Expected : pas d'erreur. `git status` montre les renames.

- [ ] **Step 2 : Déplacer `resources/` à l'intérieur du package**

```bash
mkdir -p houba
git mv resources houba/resources
```

Expected : `resources/` n'existe plus à la racine, `houba/resources/` contient le contenu.

- [ ] **Step 3 : Vérifier la nouvelle arborescence**

```bash
ls houba/
ls houba/resources/
```

Expected (sortie ressemble à) :
```
houba/__init__.py  houba/adapters/  houba/cli/  houba/config.py  houba/domain/  houba/errors.py  houba/logging.py  houba/ports/  houba/resources/
```

```
Dockerfile.template  add_sncf_http_sources.sh  add_sncf_https_sources.sh  certificats/  get_sncf_keyring.sh  install_sncf_keyring.sh  properties.yml.template  regis-playbooks.yml  set_timezone.sh  teams_notification.json  update_keystore.sh
```

- [ ] **Step 4 : Commit dédié au renommage de chemin**

```bash
git add -A
git commit -m "chore(rename): hub2hub → houba (package + resources)"
```

Expected : commit créé, contient uniquement des renames (git détecte les similarités).

---

## Task 5 : Sed 1 — `H2H_` → `HOUBA_` (préfixe variables d'environnement)

**Files :** Tous les `*.py`, `*.toml`, `*.yml`, `*.md`, `Dockerfile` hors `docs/superpowers/specs/` et `docs/superpowers/plans/`.

- [ ] **Step 1 : Exécuter le sed**

```bash
cd ~/h2h-split/houba-extract
find . -type f \
    \( -name '*.py' -o -name '*.toml' -o -name '*.yml' -o -name '*.md' -o -name 'Dockerfile' -o -name '.gitlab-ci.yml' \) \
    -not -path './docs/superpowers/specs/*' \
    -not -path './docs/superpowers/plans/*' \
    -not -path './.git/*' \
    -exec sed -i.bak 's/\bH2H_/HOUBA_/g' {} \;
find . -name '*.bak' -not -path './.git/*' -delete
```

Note : `sed -i.bak` est compatible BSD (macOS) et GNU (Linux). Le `.bak` est ensuite supprimé.

- [ ] **Step 2 : Vérifier les substitutions**

```bash
grep -rn '\bH2H_' . --include='*.py' --include='*.toml' --include='*.yml' --include='*.md' --include='Dockerfile' \
    | grep -v docs/superpowers/specs | grep -v docs/superpowers/plans | grep -v '\.git/'
```

Expected : aucun match.

```bash
grep -rn '\bHOUBA_' . --include='*.py' --include='*.toml' --include='*.yml' --include='Dockerfile' | head -10
```

Expected : matchs présents dans `houba/config.py`, `tests/`, et le Dockerfile/CI.

- [ ] **Step 3 : Vérifier que les specs et plans (références historiques) restent intacts**

```bash
grep -n '\bH2H_' docs/superpowers/specs/*.md docs/superpowers/plans/*.md | head -3
```

Expected : matchs présents (`H2H_HARBOR_URL` apparaît bien dans les specs originaux et les références historiques — c'est OK).

- [ ] **Step 4 : Vérifier que les tests passent toujours**

```bash
uv sync 2>&1 | tail -3                    # mise à jour de l'environnement
uv run pytest tests/unit/test_config.py -v
```

Expected : 7 tests passants (`test_settings_from_env`, etc.). Les tests utilisent maintenant `HOUBA_HARBOR_URL` etc. — ils doivent toujours passer car le code de production a aussi été modifié.

Si tests rouges → STOP, diagnostiquer (probablement un fichier qui a manqué la substitution).

- [ ] **Step 5 : Commit**

```bash
git add -A
git commit -m "chore(rename): H2H_ → HOUBA_ (préfixe variables d'environnement)"
```

---

## Task 6 : Sed 2 — `hub2hub` → `houba` (nom du package Python)

**Files :** Tous les `*.py`, `*.toml`, `*.yml`, `Dockerfile`.

- [ ] **Step 1 : Exécuter le sed**

```bash
cd ~/h2h-split/houba-extract
find . -type f \
    \( -name '*.py' -o -name '*.toml' -o -name '*.yml' -o -name 'Dockerfile' \) \
    -not -path './.git/*' \
    -exec sed -i.bak 's/\bhub2hub\b/houba/g' {} \;
find . -name '*.bak' -not -path './.git/*' -delete
```

Note : on inclut **pas** les `*.md` ici. Les références à `hub2hub` dans les specs/plans/docs sont historiques et doivent être préservées (cf. §4 du spec : "Substitutions exclues").

- [ ] **Step 2 : Vérifier les substitutions**

```bash
grep -rn '\bhub2hub\b' . --include='*.py' --include='*.toml' --include='*.yml' --include='Dockerfile' | grep -v '\.git/'
```

Expected : aucun match.

```bash
grep -rn '^from houba\b\|^import houba\b' houba tests --include='*.py' | head -5
```

Expected : matchs présents (imports renommés).

- [ ] **Step 3 : `uv sync` pour mettre à jour le wheel build**

```bash
uv sync 2>&1 | tail -5
```

Expected : succès. Le `[project] name = "houba"` est cohérent avec le package physique `houba/`.

- [ ] **Step 4 : Tests + mypy + ruff**

```bash
uv run pytest -v 2>&1 | tail -3
uv run mypy houba 2>&1 | tail -3
uv run ruff check houba tests 2>&1 | tail -3
```

Expected :
- `91 passed`
- `Success: no issues found in N source files`
- `All checks passed!`

Si rouge → STOP, diagnostiquer.

- [ ] **Step 5 : Commit**

```bash
git add -A
git commit -m "chore(rename): hub2hub → houba (nom du package Python)"
```

---

## Task 7 : Sed 3 — `h2h-cli` → `houba` (nom de l'image Docker)

**Files :** Dockerfile, `.gitlab-ci.yml`, runbooks éventuels.

**IMPORTANT** : cette substitution doit s'exécuter **AVANT** la Task 8 (sed `\bh2h\b`), sinon `h2h-cli` deviendrait `houba-cli` au lieu de `houba`.

- [ ] **Step 1 : Exécuter le sed**

```bash
cd ~/h2h-split/houba-extract
find . -type f \
    \( -name '*.py' -o -name '*.toml' -o -name '*.yml' -o -name '*.md' -o -name 'Dockerfile' -o -name '.gitlab-ci.yml' \) \
    -not -path './docs/superpowers/specs/*' \
    -not -path './docs/superpowers/plans/*' \
    -not -path './.git/*' \
    -exec sed -i.bak 's/h2h-cli/houba/g' {} \;
find . -name '*.bak' -not -path './.git/*' -delete
```

- [ ] **Step 2 : Vérifier**

```bash
grep -rn 'h2h-cli' . --include='*.py' --include='*.toml' --include='*.yml' --include='*.md' --include='Dockerfile' --include='.gitlab-ci.yml' \
    | grep -v docs/superpowers/specs | grep -v docs/superpowers/plans | grep -v '\.git/'
```

Expected : aucun match.

- [ ] **Step 3 : Commit**

```bash
git add -A
git commit -m "chore(rename): h2h-cli → houba (nom de l'image Docker)"
```

---

## Task 8 : Sed 4 — `\bh2h\b` → `houba` (mot entier, exclut `fr.sncf.h2h.*`)

**Files :** Tous les `*.py`, `*.toml`, `*.md`, `Dockerfile`, `.gitlab-ci.yml` hors specs/plans.

Cette substitution **ne doit pas** toucher les labels OCI `fr.sncf.h2h.*` (compatibilité `deleteProduct.groovy` — cf. spec §2 et §6.3 de Phase A). Utilisation de Perl pour disposer de lookbehind/lookahead.

- [ ] **Step 1 : Exécuter le perl**

```bash
cd ~/h2h-split/houba-extract
find . -type f \
    \( -name '*.py' -o -name '*.toml' -o -name '*.md' -o -name 'Dockerfile' -o -name '.gitlab-ci.yml' \) \
    -not -path './docs/superpowers/specs/*' \
    -not -path './docs/superpowers/plans/*' \
    -not -path './.git/*' \
    -exec perl -i -pe 's/(?<!sncf\.)\bh2h\b(?!\.)/houba/g' {} \;
```

Explication de la regex :
- `(?<!sncf\.)` : lookbehind négatif — pas précédé de "sncf."
- `\bh2h\b` : `h2h` comme mot entier
- `(?!\.)` : lookahead négatif — pas suivi d'un point (sinon ça pourrait toucher `h2h.source.registry` si on retire "sncf." en amont)

Cette double protection couvre `fr.sncf.h2h.source.registry` ET hypothétiquement `h2h.foo` standalone.

- [ ] **Step 2 : Vérifier que les labels OCI sont préservés**

```bash
grep -rn 'fr\.sncf\.h2h\.' houba tests --include='*.py' | head -10
```

Expected : matchs présents (les labels sont intacts).

- [ ] **Step 3 : Vérifier que `h2h` standalone a disparu**

```bash
grep -rn '\bh2h\b' . --include='*.py' --include='*.toml' --include='*.md' --include='Dockerfile' --include='.gitlab-ci.yml' \
    | grep -v 'fr\.sncf\.h2h' | grep -v docs/superpowers/specs | grep -v docs/superpowers/plans | grep -v '\.git/'
```

Expected : aucun match (toutes les occurrences isolées ont été substituées).

- [ ] **Step 4 : Sanity check global — tests + lint**

```bash
uv run pytest -v 2>&1 | tail -3
uv run mypy houba 2>&1 | tail -3
uv run ruff check houba tests 2>&1 | tail -3
uv run ruff format --check houba tests 2>&1 | tail -3
```

Expected : tout vert. **Si ruff format échoue** : `uv run ruff format houba tests`, puis re-vérifier.

- [ ] **Step 5 : Smoke test du CLI**

```bash
uv run houba version 2>&1                          # affiche 0.1.0.dev0
uv run houba --help 2>&1 | head -20                # liste dev et version
```

Expected : la commande s'appelle bien `houba` (et plus `h2h`). La version s'affiche.

- [ ] **Step 6 : Commit**

```bash
git add -A
git commit -m "chore(rename): h2h → houba (binary CLI, mot entier ; labels OCI préservés)"
```

---

## Task 9 : Construire un nouveau `.gitlab-ci.yml` dédié à `houba`

**Files :** Create: `.gitlab-ci.yml` (en remplaçant l'éventuel résidu du filter-repo).

Le filter-repo n'a pas inclus `.gitlab-ci.yml` (voir Task 3) donc le fichier doit être absent. On le crée frais.

- [ ] **Step 1 : Vérifier l'absence**

```bash
cd ~/h2h-split/houba-extract
ls -la .gitlab-ci.yml 2>&1
```

Expected : `No such file or directory`.

- [ ] **Step 2 : Créer le fichier**

```bash
cat > .gitlab-ci.yml <<'EOF'
# CI/CD du repo houba — CLI Python de la pipeline Hub2Hub.
# Pour le projet métier Hub2Hub (Jenkins Shared Library Groovy), voir le repo shared-libs.

stages:
  - test
  - build

.python_base:
  image: python:3.12-slim
  before_script:
    - pip install --no-cache-dir uv
    - apt-get update && apt-get install -y --no-install-recommends git ca-certificates
    - uv sync

python:lint:
  extends: .python_base
  stage: test
  script:
    - uv run ruff check .
    - uv run ruff format --check .
    - uv run mypy houba
  rules:
    - changes:
        - pyproject.toml
        - uv.lock
        - houba/**/*
        - tests/**/*
        - .gitlab-ci.yml

python:test:
  extends: .python_base
  stage: test
  script:
    - uv run pytest tests/ -v --cov=houba --cov-report=term-missing --cov-fail-under=80
    - uv run pytest tests/unit/domain -v --cov=houba.domain --cov-report=term-missing --cov-fail-under=90
  artifacts:
    when: always
    paths:
      - .coverage
    expire_in: 1 week
  rules:
    - changes:
        - pyproject.toml
        - uv.lock
        - houba/**/*
        - tests/**/*

python:build:image:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  variables:
    DOCKER_TLS_CERTDIR: ""
  script:
    - docker build -t houba:${CI_COMMIT_SHORT_SHA} .
  rules:
    - if: $CI_COMMIT_BRANCH
      changes:
        - Dockerfile
        - pyproject.toml
        - uv.lock
        - houba/**/*
EOF
```

- [ ] **Step 3 : Vérifier la syntaxe YAML**

```bash
uv run python -c "import yaml; yaml.safe_load(open('.gitlab-ci.yml'))"
```

Expected : pas d'erreur.

- [ ] **Step 4 : Commit**

```bash
git add .gitlab-ci.yml
git commit -m "ci: nouveau .gitlab-ci.yml dédié à houba (lint + test + build:image)"
```

---

## Task 10 : Vérification globale post-extraction

**Files :** Aucune modification.

- [ ] **Step 1 : Sanity grep — aucun reste de `hub2hub`/`H2H_`/`h2h` standalone**

```bash
cd ~/h2h-split/houba-extract
echo "=== hub2hub résiduel ==="
grep -rn '\bhub2hub\b' . --include='*.py' --include='*.toml' --include='*.yml' --include='Dockerfile' --include='.gitlab-ci.yml' \
    | grep -v docs/superpowers/ | grep -v '\.git/' \
    || echo "OK aucun"

echo "=== H2H_ résiduel ==="
grep -rn '\bH2H_' . --include='*.py' --include='*.toml' --include='*.yml' --include='Dockerfile' --include='.gitlab-ci.yml' \
    | grep -v docs/superpowers/ | grep -v '\.git/' \
    || echo "OK aucun"

echo "=== h2h standalone (hors fr.sncf.h2h.) ==="
grep -rn '\bh2h\b' . --include='*.py' --include='*.toml' --include='Dockerfile' --include='.gitlab-ci.yml' \
    | grep -v 'fr\.sncf\.h2h' | grep -v docs/superpowers/ | grep -v '\.git/' \
    || echo "OK aucun"

echo "=== labels OCI préservés ==="
grep -rn 'fr\.sncf\.h2h' houba tests --include='*.py' | head -5
```

Expected : 3 premiers checks renvoient "OK aucun". Le 4e renvoie des matchs (labels intacts).

- [ ] **Step 2 : Tests + lint complet**

```bash
uv run ruff check . 2>&1 | tail -3
uv run ruff format --check . 2>&1 | tail -3
uv run mypy houba 2>&1 | tail -3
uv run pytest -v --cov=houba --cov-report=term-missing --cov-fail-under=80 2>&1 | tail -5
uv run pytest tests/unit/domain -v --cov=houba.domain --cov-fail-under=90 2>&1 | tail -3
```

Expected :
- ruff check : `All checks passed!`
- ruff format : `N files already formatted`
- mypy : `Success: no issues found in N source files`
- pytest global : `91 passed`, coverage ≥ 80 %
- pytest domain : `39 passed`, coverage ≥ 90 %

- [ ] **Step 3 : Build Docker + smoke**

```bash
docker build -t houba:phase-a .
docker run --rm houba:phase-a version
docker run --rm houba:phase-a --help
docker run --rm houba:phase-a dev --help
docker run --rm houba:phase-a dev capture --help
```

Expected :
- Build réussi
- `houba:phase-a version` affiche `0.1.0.dev0`
- `--help` montre `version` et `dev` comme commands
- `dev --help` montre `capture`
- `dev capture --help` montre `--project`, `--repository`, `--output`

- [ ] **Step 4 : Vérifier le compte de commits préservés**

```bash
git log --oneline | wc -l
```

Expected : ≥ 30 (les 35 commits Phase A initiaux + 5 commits de rename = ~40).

```bash
git log --oneline -5    # les derniers commits sont les renames
```

Expected : les 5 derniers commits sont les `chore(rename): …` créés par Tasks 4-8 + le commit `ci: nouveau .gitlab-ci.yml` de Task 9.

- [ ] **Step 5 : Poser le tag**

```bash
git tag -a v0.1.0-phase-a -m "Phase A — fondations + couche domain/ (post-extraction houba)"
git log --oneline v0.1.0-phase-a | head -1
```

Expected : tag créé sur le HEAD.

---

## Task 11 : Créer le repo `houba` sur GitLab et push

**Files :** Aucune modification locale.

- [ ] **Step 1 : Créer le repo sur GitLab SNCF**

Action humaine (UI ou API GitLab) :
- Créer un nouveau projet `houba` dans le groupe approprié sur `gitlab-repo-gpf.apps.eul.sncf.fr`.
- Ne PAS initialiser avec un README (on pousse une histoire existante).
- Récupérer l'URL HTTPS ou SSH du repo.

- [ ] **Step 2 : Configurer le remote local**

```bash
cd ~/h2h-split/houba-extract
git remote -v             # vérifie l'absence de origin (filter-repo l'a supprimé)
git remote add origin <houba-url>
```

- [ ] **Step 3 : Push `master` + tag**

```bash
git push -u origin extract:master
git push origin v0.1.0-phase-a
```

Expected : push acceptés. Le repo houba a maintenant `master` et le tag.

- [ ] **Step 4 : Vérification distante**

```bash
git ls-remote origin
```

Expected : montre `refs/heads/master` et `refs/tags/v0.1.0-phase-a`.

- [ ] **Step 5 : Re-clone propre depuis houba pour valider**

```bash
cd ~
git clone <houba-url> ~/Documents/Workspaces/ttc/houba
cd ~/Documents/Workspaces/ttc/houba
uv sync
uv run pytest -v 2>&1 | tail -3
docker build -t houba:from-fresh-clone .
docker run --rm houba:from-fresh-clone version
```

Expected : 91 tests verts, build OK, `houba version` répond.

C'est le test ultime que l'extraction est viable : un développeur qui clone le repo `houba` à zéro doit pouvoir tout faire fonctionner.

---

## Task 12 : Nettoyage agressif de `shared-libs`

**Files :**
- Supprimer : `hub2hub/`, `tests/`, `pyproject.toml`, `uv.lock`, `.python-version`, `Dockerfile`, `.dockerignore`, `resources/`, `docs/superpowers/`
- Modifier : `.gitlab-ci.yml` (retrait des jobs `python:*`)
- Créer/modifier : `README.md` (mention de houba)

Cette tâche se fait dans le repo `shared-libs` principal (pas le worktree extraction), sur une branche dédiée.

- [ ] **Step 1 : Préparer la branche**

```bash
cd /Users/tristan/Documents/Workspaces/ttc/shared-libs
git checkout master
git pull --ff-only origin master
git checkout -b chore/post-houba-cleanup
```

- [ ] **Step 2 : Supprimer les fichiers et répertoires Python**

```bash
git rm -r hub2hub/ tests/ resources/ docs/superpowers/
git rm pyproject.toml uv.lock .python-version Dockerfile .dockerignore
```

Expected : `git status` montre les suppressions.

- [ ] **Step 3 : Nettoyer `.gitlab-ci.yml`**

La section Python a été ajoutée par Task 21 de Phase A et commence par le marker `# ──────────────── Python (Phase A) ────────────────`. La section inclut le bloc `stages:`, l'anchor `.python_base`, et les jobs `python:lint`, `python:test`, `python:build:image`. Suppression d'un coup :

```bash
# Vérifier la présence du marker
grep -n "Python (Phase A)" .gitlab-ci.yml
```

Expected : une ligne, par exemple `150:# ──────────────── Python (Phase A) ────────────────`.

```bash
# Supprimer du marker jusqu'à la fin du fichier
sed -i.bak '/^# ──.*Python (Phase A)/,$d' .gitlab-ci.yml
rm .gitlab-ci.yml.bak
```

Note : sed BSD (macOS) et GNU acceptent tous deux `-i.bak`. La range `/<motif>/,$d` supprime depuis la première ligne matchant jusqu'à la fin (`$`).

Vérification :

```bash
grep -c '^python:\|^\.python_base\|Python (Phase A)' .gitlab-ci.yml
```

Expected : `0`.

```bash
tail -5 .gitlab-ci.yml
```

Expected : les 5 dernières lignes sont à nouveau celles de la section Groovy d'origine (par exemple le job `restore-archive` ou `update-proxycaches`).

```bash
git add .gitlab-ci.yml
git diff --cached .gitlab-ci.yml | head -20    # contrôle visuel des suppressions
```

- [ ] **Step 4 : Mettre à jour le README**

Si `README.md` n'existe pas, le créer. Sinon ajouter le bloc suivant en haut :

```markdown
> **Note** : Le CLI Python qui orchestre les imports Hub2Hub a été extrait
> dans le repo dédié [`houba`](<houba-url>). Ce repo `shared-libs` conserve
> uniquement la Jenkins Shared Library Groovy (`vars/`) et le legacy Python
> (`ci/`) en attente de décommission. Voir
> [docs/superpowers/specs/2026-05-21-extraction-houba-design.md](#)
> dans le repo `houba` pour le contexte de l'extraction.
```

Remplacer `<houba-url>` par l'URL réelle obtenue à la Task 11.

```bash
git add README.md
```

- [ ] **Step 5 : Commit unique du cleanup**

```bash
git commit -m "chore: extraction du Python vers le repo houba

Suite à l'extraction documentée dans le spec
docs/superpowers/specs/2026-05-21-extraction-houba-design.md (référencé
depuis le repo houba désormais).

Tag de jonction : pre-houba-extract.

Supprimé de ce repo :
- hub2hub/ (le package CLI, désormais houba/ dans le repo houba)
- tests/ (suite pytest)
- pyproject.toml, uv.lock, .python-version (gestion projet Python)
- Dockerfile, .dockerignore
- resources/ (templates Dockerfile, scripts SNCF, certificats)
- docs/superpowers/ (specs et plans Phase A)
- Jobs python:* du .gitlab-ci.yml

Conservé :
- vars/ (Jenkins Shared Library Groovy)
- ci/ (legacy Python à décommissionner en Phase B-E côté houba)
- .gitlab-ci.yml (jobs Groovy + restore-archive)
- .groovylintrc.json"
```

- [ ] **Step 6 : Push et MR**

```bash
git push -u origin chore/post-houba-cleanup
```

Créer la merge request via UI ou `glab` :

```bash
glab mr create --title "chore: extraction du Python vers le repo houba" \
    --description "Voir docs/superpowers/specs/2026-05-21-extraction-houba-design.md du repo houba." \
    --target-branch master
```

- [ ] **Step 7 : Vérification post-MR (après merge)**

Une fois la MR mergée :

```bash
cd /Users/tristan/Documents/Workspaces/ttc/shared-libs
git checkout master
git pull --ff-only origin master
ls -la                       # plus de hub2hub/, tests/, etc.
grep -c 'python:' .gitlab-ci.yml || echo "OK aucun job python"
```

Expected :
- Répertoires `hub2hub/`, `tests/`, `resources/`, `docs/superpowers/` absents
- Fichiers `pyproject.toml`, `uv.lock`, `Dockerfile`, etc. absents
- `.gitlab-ci.yml` n'a plus de job python

---

## Task 13 : Démanteler le worktree extraction et clore l'opération

**Files :** Aucune modification.

- [ ] **Step 1 : Supprimer le worktree de l'extraction**

```bash
cd /Users/tristan/Documents/Workspaces/ttc/shared-libs
git worktree list
git worktree remove .claude/worktrees/mystifying-montalcini-2ee38b
```

Expected : worktree supprimé proprement. Si `git worktree remove` se plaint d'un fichier non-commit, utiliser `--force` après avoir vérifié qu'il n'y a rien à sauver.

- [ ] **Step 2 : Supprimer le clone temporaire**

```bash
rm -rf ~/h2h-split/houba-extract
rmdir ~/h2h-split 2>/dev/null || true
```

- [ ] **Step 3 : Pinger les éventuels consommateurs**

Action humaine : prévenir les équipes consommatrices que le tag `pre-houba-extract` de `shared-libs` marque le point de bascule, et que toute évolution future de l'outil Python se fera dans le repo `houba`.

- [ ] **Step 4 : Mise à jour de la doc d'équipe (Confluence / Notion)**

Action humaine : ajouter le lien vers le repo houba dans la page d'onboarding, à côté de celui de shared-libs.

- [ ] **Step 5 : Verrouiller / archiver `shared-libs/origin/master` éventuel pour les fichiers Python**

Action humaine : éventuellement protéger les chemins Python en MR rules sur shared-libs (interdire la création d'un nouveau `hub2hub/` ou `pyproject.toml` dedans).

---

## Critères d'acceptation globaux

L'extraction est terminée quand TOUS ces critères sont satisfaits :

**Côté `houba`** :
- [ ] Repo `houba` créé sur GitLab SNCF, branche `master` reçue, tag `v0.1.0-phase-a` posé.
- [ ] `git log --oneline | wc -l` ≥ 30 (historique préservé par `filter-repo`).
- [ ] `uv sync` réussit depuis un clone neuf.
- [ ] `uv run pytest -v` : 91 tests passent.
- [ ] Coverage global ≥ 80 %, `houba.domain` ≥ 90 %.
- [ ] `uv run mypy houba` clean.
- [ ] `uv run ruff check . && uv run ruff format --check .` clean.
- [ ] `docker build -t houba:phase-a .` réussit.
- [ ] `docker run --rm houba:phase-a version` affiche `0.1.0.dev0`.
- [ ] `docker run --rm houba:phase-a --help` liste `version` et `dev`.
- [ ] `grep -rn '\bhub2hub\b' houba tests pyproject.toml Dockerfile .gitlab-ci.yml` : zéro match (hors docs).
- [ ] `grep -rn '\bH2H_' houba tests pyproject.toml Dockerfile .gitlab-ci.yml` : zéro match (hors docs).
- [ ] `grep -rn 'fr\.sncf\.h2h' houba tests` : matchs préservés (labels OCI).
- [ ] Pipeline GitLab CI vert sur `master`.

**Côté `shared-libs`** :
- [ ] Tag `pre-houba-extract` poussé sur `origin`.
- [ ] Branche `chore/post-houba-cleanup` mergée dans `master`.
- [ ] Plus aucun fichier Python (`grep -l 'hub2hub' .` retourne rien).
- [ ] `.gitlab-ci.yml` débarrassé des jobs `python:*`.
- [ ] README pointe vers `houba`.
- [ ] Pipeline CI vert après cleanup.

**Logistique** :
- [ ] Worktree `mystifying-montalcini-2ee38b` supprimé.
- [ ] Clone temporaire `~/h2h-split/houba-extract/` supprimé.
- [ ] Équipe(s) prévenue(s).

---

## Plan de rollback

Voir spec §7. En résumé :

| Stade | Action de rollback |
|---|---|
| Houba pas encore pushé | `rm -rf ~/h2h-split/houba-extract` |
| Houba pushé, shared-libs intact | Archive `houba` côté GitLab. ~10 min. |
| Tout pushé et mergé | Revert la MR `chore/post-houba-cleanup`. Archive `houba`. Re-pousser sur shared-libs si Phase B déjà entamée. ~30 min. |

Les déclencheurs de rollback (régression de tests, mypy red, Docker KO, refus GitLab) sont détaillés dans la spec.
