# Icônes du menu de navigation

> 🔴 **Ce document ne recense plus les icônes.** Son tableau « Icône actuelle » était
> faux pour dix routes sur treize — sept icônes changées depuis, et trois routes
> (`/actualites`, `/calendrier`, `/acces-securite`) qui ne sont plus des entrées du
> menu — et il ignorait `/delegations` (#1049, audit du 19/09/2026, recompté le
> 24/09). Une copie d'une table de code diverge au
> premier changement ; la table se lit donc là où elle vit.

## Où lire l'icône d'une entrée

| Question | Source |
|---|---|
| Icône par défaut d'une page accessible à tous | `front/src/lib/pages.ts` — champ `icone` de chaque page |
| Icône d'une page réservée à un rôle (Espace CS, Paramétrage…) | `front/src/lib/pages-roles.ts` |
| Icône réellement servie | `front/src/lib/pages-surcharge.ts` : l'icône est **administrable** (Admin › Présentation › Menu et pages) ; une surcharge absente retombe sur la valeur de `pages.ts` |
| Noms d'icônes disponibles | `front/src/lib/icones-svg.json` — un nom inconnu échoue **en silence** : le vérifier avant de l'écrire |
| Rendu | `front/src/lib/components/Icon.svelte` (icônes Lucide, SVG monochrome) — catalogue : https://lucide.dev/icons/ |
| Licence et origine des tracés | Lucide (ISC ; MIT pour la part issue de Feather), sauf les icônes de `ICONES_HORS_LUCIDE` (`scripts/ci/licences_politique.py`) — une icône qui ne vient pas de Lucide s'y déclare, avec son contenu tiers et `REUSE.toml` (#1543) |

## Ce qui reste valable des choix d'origine

- Deux entrées voisines ne portent pas la même image : l'accueil et « Mon lot » ne
  sont pas deux maisons, l'Espace CS et le Paramétrage ne sont pas le même
  bouclier.
- Une « affaire » n'est pas un billet : pas de `ticket`, qui évoque la billetterie.
