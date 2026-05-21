# Runbook — Capture de fixtures Hub2Hub

## But

Constituer un jeu de fixtures Harbor depuis la prod pour le développement et
les snapshot tests de la Phase A.

## Pré-requis

- Accès lecture au Harbor de production (`HOUBA_HARBOR_URL`, robot account
  read-only `pic-dosn_hcr-prod-sharedlibs` ou équivalent).
- Variables d'environnement `HOUBA_*` valorisées (cf. spec §6.1).
- Image `h2h-cli` buildée localement (`docker build -t h2h-cli:dev .`) ou
  exécution via `uv run h2h`.

## Sélection des produits

Capturer **au moins** un produit pour chacun des cas suivants :

| Cas                                | Suggestion             |
|------------------------------------|------------------------|
| Produit simple (peu de tags)       | `library/busybox`      |
| Produit semver dense               | `rancher/k3s`          |
| Produit avec EOL                   | `library/redis`        |
| Produit avec exclusions regex      | (à choisir)            |
| Produit avec digest changeant      | `library/nginx:stable` |
| Produit multi-tag (alias)          | (à choisir)            |
| Produit déjà archivé               | (à choisir)            |
| Produit avec proxy-cache amont     | (à choisir)            |

Au total : viser 10 à 20 captures.

## Procédure

Pour chaque produit retenu :

```bash
uv run h2h dev capture \
  --project <project> \
  --repository <repository> \
  --output tests/fixtures/captured/
```

## Anonymisation

Avant commit : grep le contenu pour vérifier qu'aucune donnée sensible n'a fuité.
Les noms d'agents (`robot$…`), URLs internes et tokens ne doivent **pas**
apparaître dans les fichiers JSON.

## Commit

```bash
git add tests/fixtures/captured/
git commit -m "test(fixtures): capture initiale de N fixtures Harbor prod"
```
