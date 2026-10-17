---
adr: SDR-0000
slug: socle-de-service
title: Socle de service
status: rejected
revision: 1
date: 2026-10-17
authors: [Tristan Rivoallan]
supersedes: []
---

# Socle de service

> **Version expurgée.** Cet ADR est hérité de la méthode surdesrails. Sa
> version amont décrit le socle d'un service interne à l'organisation qui
> publie la méthode : ses principes de service, et le référentiel où ce
> service rattache ses métriques de coût. Ce contenu est propre à cette
> organisation, et ce dépôt est public : il n'est pas reproduit ici. Seuls
> la question et le verdict sont conservés.

## Context and Problem Statement

La méthode demande à quel centre de coût ce dépôt rattache les métriques
FinOps qu'il expose : les métriques qui rapportent une consommation
d'infrastructure à ce qu'elle coûte, et à qui la consomme. Le rattachement se
fait par un identifiant, pris dans le référentiel de facturation de
l'organisation. La question suppose donc un dépôt qui sert un client
facturable dans cette organisation.

## Considered Options

* **Écrire l'identifiant de rattachement** : les métriques exposées deviennent facturables.
* **Exposer les métriques sans les rattacher** : elles s'observent, mais personne ne les facture.
* **`rejected`** : le dépôt ne produit aucune métrique FinOps, parce qu'il ne sert aucun client facturable. Le motif dit ce qui en tient lieu.

## Decision Outcome

Écart : `rejected`. knock est un CLI public open source. Il ne sert aucun
client facturable et n'expose aucune métrique FinOps : il n'a donc pas
d'identifiant de rattachement (répondue le 2026-10-17). Ce qui en tient
lieu : l'organisation qui exécute knock rattache sa propre exécution
(CronJob, Argo) à son centre de coût.

### Consequences

Ce dépôt n'a aucun rattachement FinOps à tenir, et il reste générique
(`CLAUDE.md` : « no organization-specific references »).
Le coût d'exécution de knock n'est visible que chez l'adoptant.
