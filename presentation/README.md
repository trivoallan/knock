# houba — presentation decks

Slidev decks for talking through houba. Two audiences:

- **`slides.md`** — *architecture deck* (English). A narrative tour of the
  architecture, mirrors `docs/explanation/architecture.md`.
- **`houba-fr.md`** — *équipe & management deck* (français). Le pourquoi (la
  valeur), le quoi (le produit), le comment (l'architecture) et l'état du projet —
  pour présenter houba à un·e responsable et une équipe.

```bash
npx @slidev/cli@latest houba-fr.md        # serveur de dev (live)
npx @slidev/cli@latest build houba-fr.md  # build statique dans dist/
npx @slidev/cli@latest export houba-fr.md # export PDF (--format pdf)
```

Swap the filename for `slides.md` to run the architecture deck instead.

Local talk artifacts — not published by CI.
