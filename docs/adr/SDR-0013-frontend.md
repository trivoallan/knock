---
adr: SDR-0013
slug: frontend
title: Frontend
status: rejected
revision: 1
date: 2026-10-17
authors: [Tristan Rivoallan]
supersedes: []
---

# Frontend

> **Version expurgée.** Cet ADR est hérité de la méthode surdesrails. Sa
> version amont prescrit le framework front et le design system de
> l'organisation qui publie la méthode, avec leurs thèmes, leurs paquets et
> les règles que l'agent applique en écrivant une interface. Ce contenu est
> propre à cette organisation, et ce dépôt est public : il n'est pas
> reproduit ici. Seuls la question et le verdict sont conservés.

## Context and Problem Statement

La méthode demande avec quel framework et quel design system ce dépôt écrit
son interface. Sans réponse, un agent qui écrit une interface choisit
lui-même le framework, le design system et les skills, et il choisit
autrement au projet suivant.

## Considered Options

* **Le framework et le design system que la méthode prescrit**, avec le thème de l'entité qui porte le dépôt.
* **Un autre framework**, à justifier dans un ADR local.
* **`rejected`** : le dépôt ne livre pas d'interface. Le motif dit ce qui en tient lieu.

## Decision Outcome

Écart : `rejected` (répondue le 2026-10-17). knock est un CLI Typer sans
interface. Aucun framework ni design system n'en tient lieu.

### Consequences

L'agent n'applique aucune règle d'interface à ce dépôt.
Une interface future, comme le portail de couverture (*Later* dans la
roadmap), vivrait hors de knock.
