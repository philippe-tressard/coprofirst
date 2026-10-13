# Spécifications — spécification d'origine

> ⚠️ **Document historique : le site a évolué depuis, et le manuel fait foi.**
> Ces fichiers décrivent le produit tel qu'il a été **conçu** — pas tel qu'il est.
> Plusieurs écrans qu'ils nomment ont été fusionnés ou retirés depuis (la page
> *Accès & badges*, *Transparence & gouvernance*, les *publications* et le
> *calendrier* comme pages distinctes — devenus des affaires et leurs filtres).
> Pour ce que le site fait **aujourd'hui** : le
> [manuel utilisateur](../docs/manuel-utilisateur.html) (ce que chaque écran contient
> et qui peut le voir) et le [README](../README.md) (ce que le produit est).
> Pour ce que le code **impose** : `CLAUDE.md` et `.claude/skills/` à la racine du dépôt.

Aucun contrôle de la CI ne confronte ces fichiers au code : ils ne sont **pas
tenus à jour**, et une contradiction avec le manuel se tranche toujours en faveur
du manuel.

## Contenu

| Dossier | Ce qu'il contient |
|---|---|
| [`commun/`](commun/) | Contexte et objectifs, personas, cas d'utilisation, glossaire |
| [`web/`](web/) | Exigences et navigation du site web |
| [`mobile/`](mobile/) | Exigences et navigation de la PWA |
| [`design/`](design/) | Charte graphique, principes UX, parcours utilisateurs |
| [`architecture/`](architecture/) | Vue d'ensemble, pile technique, modèle de données, API |

> 🧭 **Deux exceptions**, qui ne sont pas historiques et se tiennent à jour à
> chaque arbitrage : [`architecture/multi-coproprietes.md`](architecture/multi-coproprietes.md),
> l'architecture **cible** du chantier multi-copropriétés, et
> [`architecture/mode-demo.md`](architecture/mode-demo.md), l'installation de
> démonstration publique.

La partie qui vieillit le plus vite est la **navigation** (`web/navigation.md`,
`mobile/navigation.md`) : l'arborescence des écrans change à chaque lot.
Les noms de tables, de routes et de modèles de `architecture/` sont, eux aussi, ceux
de la conception — le code (`api/app/models/`) fait foi.
