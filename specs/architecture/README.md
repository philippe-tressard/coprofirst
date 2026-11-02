# Architecture technique

> ⚠️ **Spécification d'origine** — le site a évolué depuis, le [manuel utilisateur](../../docs/manuel-utilisateur.html) fait foi (voir [`specs/README.md`](../README.md)).

## Sommaire

- [Vue d'ensemble](vue-ensemble.md)
- [Stack technique](stack.md)
- [Modèle de données](modele-donnees.md)
- [Lots, circulations et périmètres](lots-et-perimetres.md) — la règle générale d'un règlement de copropriété : un lot est situé dans un bâtiment, desservi par une circulation, et contribue à des clés de charges ; l'impact sur la visibilité et les badges
- [API](api.md)

## Cible

- [Conservation des affaires](conservation-affaires.md) — **en conception** (16/10/2026, #2014) : à l'échéance (10, 5 ou 2 exercices selon la catégorie), une affaire perd ses pièces jointes, archivées sur le PC, et ses auteurs, et garde son texte.
- [Notifications push](notifications-push.md) — **en conception** (02/11/2026, #2458) : le relais APNs de la plateforme, seul détenteur de la clé d'Apple ; une installation l'appelle par une requête signée et son bail, la charge ne porte aucune donnée personnelle. Pour l'application iOS native, qui s'ajoute à la PWA ([stack.md § Application mobile](stack.md#application-mobile), #2460).
- [Multi-copropriétés](multi-coproprietes.md) — **architecture cible, en conception** (07/10/2026) : une application, une base PostgreSQL par copropriété, chaque copropriété un caisson étanche. Ce fichier, lui, n'est pas historique : il se tient à jour à chaque arbitrage.
