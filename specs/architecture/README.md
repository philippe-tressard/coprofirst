# Architecture technique

> ⚠️ **Spécification d'origine** — le site a évolué depuis, le [manuel utilisateur](../../docs/manuel-utilisateur.html) fait foi (voir [`specs/README.md`](../README.md)).

## Sommaire

- [Vue d'ensemble](vue-ensemble.md)
- [Stack technique](stack.md)
- [Modèle de données](modele-donnees.md)
- [API](api.md)

## Cible

- [Conservation des affaires](conservation-affaires.md) — **en conception** (16/10/2026, #2014) : à l'échéance (10, 5 ou 2 exercices selon la catégorie), une affaire perd ses pièces jointes, archivées sur le PC, et ses auteurs, et garde son texte.
- [Multi-copropriétés](multi-coproprietes.md) — **architecture cible, en conception** (07/10/2026) : une application, une base PostgreSQL par copropriété, chaque copropriété un caisson étanche. Ce fichier, lui, n'est pas historique : il se tient à jour à chaque arbitrage.
