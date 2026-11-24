---
name: ux-patterns
description: "Motifs d'interface de 5Hostachy, et le registre de leurs arbitrages : écran, composant, libellé — carte de liste, onglets, pastilles, badges, périmètre, destinataires, champs et sections de formulaire, en-tête de page, galerie, kanban, droits à l'écran, charte, mouvement — et la checklist front avant commit. À charger : avant d'écrire ou de revoir un écran, un composant ou un libellé, et avant tout commit qui touche front/src. SKILL.md porte le sommaire et la checklist ; chaque § vit dans une annexe chargée à la demande."
argument-hint: "Describe the UX element to implement or review (e.g. 'add tabs to page fournisseurs', 'review badge consistency')"
---

# UX Patterns — 5Hostachy

Guide de référence des patterns UX établis. Tout pattern utilisé ≥ 2 fois doit être uniforme sur **toutes** les occurrences du site.

## Règle d'uniformisation

> 📖 **La règle générale est dans `standards/11-interface-et-ux.md` §1 et §1 bis** —
> regarder les autres écrans **avant** d'écrire, y compris pour ce qui n'a pas de
> nom (en-tête, titre, section, bloc, pied de page, espacement, ordre des boutons) ;
> corriger l'écart trouvé s'il est simple, ouvrir un ticket sinon ; et se méfier de
> l'**héritage partiel** quand on redéfinit localement une règle globale.
> Ne pas la recopier ici : cette skill ne porte que son instanciation 5Hostachy.

1. **Avant** d'implémenter, vérifier si un pattern similaire existe déjà (grep / semantic search) **et lire les entrées de [`ARBITRAGES.md`](ARBITRAGES.md) qui touchent la notion**
2. Si le pattern existe ≥ 2 fois → c'est un **pattern établi** → l'appliquer à l'identique
3. Si la demande contredit un pattern **ou un arbitrage** → **signaler le conflit** (pour un arbitrage : son n°, sa date, son pourquoi) et demander confirmation
4. Après implémentation → mettre à jour **cette skill** si le pattern a évolué, **et le registre** si une décision a été prise

**Où chercher, ici** : les règles globales vivent dans `front/src/styles/*.css`, importées par `app.css` — qui n'en porte plus **aucune** depuis le 27/08/2026 (#453). `composants.css` porte les classes partagées (`.carte-liste`,
`.page-header`, `.form-actions`, `.clamp-5`, `.chevron`, `.largeur-saisie`…) —
c'est le premier endroit à lire, avant toute règle locale. Les composants partagés
sont dans `front/src/lib/components/`.

⚠️ **Deux fois déjà, une page a réécrit chez elle une règle que `src/styles/` portait
déjà** : `.form-actions` (identique, donc inerte, supprimée le 15/08) et
`.page-header` (réécrite dans six pages et surchargée en ligne dans six autres —
issue #363, qui a projeté le titre de *Nouveau ticket* à droite de l'écran). Le
réflexe n'est pas « qu'est-ce que j'ajoute ? » mais « de quoi est-ce que j'hérite ? ».

## 🔴 CE QUI EST TRANCHÉ — le registre des arbitrages

Les décisions d'interface vivent dans **[`ARBITRAGES.md`](ARBITRAGES.md)**, à côté de
cette skill : numéro, statut, date, ticket, qui a tranché, **pourquoi**, ce qui a été
**écarté**, et le contrôle qui la tient. Elles s'appliquent **sans rediscuter** ; une
demande qui en défait une se signale d'abord, et si elle est maintenue, l'entrée passe
`remplacé par n° X` — jamais effacée.

**L'ouvrir avant d'écrire** : `grep -n "^### n° [0-9]" .claude/skills/ux-patterns/ARBITRAGES.md`,
puis la notion. Cette skill développe la règle ; le registre dit d'où elle vient, et
**il ne la recopie pas** : deux versions d'une même règle divergent au premier lot.

⚠️ Ce bloc était un tableau de 21 décisions, sans raison ni ticket. Le 18/10/2026, le
relevé qui l'a remplacé a trouvé **cinq paragraphes** de cette skill qui contredisaient
un arbitrage plus récent sans le dire — l'interface les avait suivis, pas le texte. Ils
portent désormais un ⚠️ qui renvoie au numéro.

Les onze premiers arbitrages (17–18/08/2026) ont tous été **constatés à l'écran** avant
d'être écrits, et trois **contredisaient** une version antérieure de cette skill : c'est
le mécanisme — *une règle d'interface se vérifie sur un écran, pas sur du papier*.

### ⚠️ Les trois pièges que ces onze arbitrages ont révélés

**1. Une objection juste dans l'absolu peut être hors sujet ici.** J'ai refusé la
carte entière comme cible de clic — « elle intercepte la sélection de texte ».
L'argument est réel et ne s'appliquait pas : le corps déplié arrête déjà la
propagation, et la zone repliée n'a rien à sélectionner. **Trois allers-retours**
ont été perdus à défendre une objection valide au mauvais endroit.

**2. Quand un écran sert de référence, il est le premier à devoir suivre la règle
qu'on en tire.** Le fil d'activité a été désigné comme modèle du geste — et c'est
lui qui a gardé l'ancien comportement le plus longtemps, parce que la règle a été
appliquée à ses imitateurs sans être remontée au modèle.

**3. Un garde-fou qui refuse dit souvent que le code est au MAUVAIS ENDROIT, pas
qu'il est trop long.** Le contrôle de modularité a refusé cinq ajouts de deux
lignes le 18/08 ; quatre fois j'ai raboté (#453), la cinquième la bonne réponse
était de **remonter la règle dans `src/styles/`** — et les deux pages y ont perdu des
lignes. Trois réponses possibles, une seule mauvaise :

| Réponse | Quand |
|---|---|
| découper le fichier | l'ajout est propre à cet écran |
| **remonter la règle d'un cran** | l'ajout dit quelque chose de **global** |
| raboter pour passer sous le seuil | ❌ jamais |

### Ce qui n'a PAS bougé

Le cadre lui-même — **ses sections, les 4 rendus, les 3 motifs de divergence** —
n'a pas changé d'une ligne en deux jours. Ce sont les **entités** qui ont appris,
pas la grammaire. C'est le signe que la grammaire est la bonne.

## Sommaire — où vit chaque §

Cette skill passait 3 000 lignes : une lecture par défaut s'arrêtait avant la checklist
(#2910). Elle est découpée en annexes, chargées à la demande ; la checklist reste ici,
juste en dessous.

| § | Sujet | Fichier |
|---|---|---|
| §0 à §0 ter | Le cadre d'une entité, l'objet Documents, la liste au-dessus du formulaire | `CADRE.md` |
| §1 à §2 bis | Icônes de contexte, périmètre, destinataires | `AFFICHAGE.md` |
| §3 | La carte expansible | `CARTES.md` |
| §4 à §8 | Onglets, pastilles, recherche, aperçu, archivage | `LISTES.md` |
| §9 à §9 quater bis | Champs de formulaire | `FORMULAIRES.md` |
| §9 sexies à §9 quinquies | L'ordre des sections, les sections communes, la soumission | `SECTIONS.md` |
| §10 à §12 | Fil d'évolutions, galerie de photos, visibilité du Kanban | `FIL-ET-GALERIE.md` |
| §13 à §14 | En-tête de page, mode lu sur l'icône, formulaire de création | `ENTETES.md` |
| §15 à §18 | Droits, workflow et archivage, mouvement, charte | `DROITS-ET-CHARTE.md` |
| — | Le registre des décisions (qui a tranché quoi, quand) | `ARBITRAGES.md` |

## Checklist UX (à vérifier avant commit)

**La seule liste**, venue de `CLAUDE.md` le 12/11/2026 (#2709) : `CLAUDE.md` n'en garde que
les quatre règles du front. Presque chaque ligne est tenue par un `npm run lint:*` ; le
détail de chaque motif est plus haut dans cette skill.

- [ ] Import d'un module de `src/lib` : `#lib/<fichier>.<extension>`, extension obligatoire
      (un dossier : `#lib/<dossier>/index.ts`) — champ `imports` de `front/package.json`
      (#2278, `npm run lint:alias-lib`)
- [ ] Pattern existant réutilisé, pas de variante ad hoc — aucun garde-fou ne le tient : la
      relecture le porte
- [ ] Méta visible en mode replié : `EnteteCarte` porte les tags (`npm run lint:entete-carte`)
- [ ] Carte de liste : `<CarteListe>` — conteneur, gouttière (`quand`, `classe`), geste
      (`onDeplier`), états (`expanded`, `urgent`, `archive`) ; jamais un `.carte-liste` à la
      main ni un `<Gouttiere>` rendu par la carte (`npm run lint:carte-liste`)
- [ ] Corps déplié d'une carte : `class="carte-corps …"` (le fondu de 200 ms) — `npm run
      lint:entete-carte` l'exige (#1579). Un survol réservé à la souris vit sous
      `@media (hover: hover) and (pointer: fine)` (§17)
- [ ] Dernière ligne d'une carte d'affaire, d'actualité ou du fil : `PastillesAffaire`,
      l'auteur par `AuteurCarte` (« ✍️ Nom ») ; ordre et exceptions au §3 (`npm run
      lint:pastilles`)
- [ ] `.clamp-3` sur l'aperçu d'une carte (`.clamp-5` hors carte) ; aucune troncature hors de
      `normes.css` (`npm run lint:clamp`)
- [ ] Un assainisseur de `#lib/sanitize` (`safeHtml`, `safeRichContent`, `safeDescription`)
      sur tout `{@html}`, jamais un helper local
      (`npm run lint:html`)
- [ ] Accessibilité : `role`, `tabindex`, `aria-label`, `on:keydown`
- [ ] Droits jamais recomposés dans un écran : `$estModerateur` (inclut admin ; il LIT
      `UserRead.est_moderateur`, servi par `auth/deps.est_moderateur`, que l'app iOS lit
      aussi, #2633), `$isProprioOuCS`, `aRole(u, …)`, ou le geste SERVI avec l'objet
      (`peut_*` ; le crayon d'une affaire : `peut_corriger`) — `npm run lint:droits`
- [ ] Une entrée de menu se montre par le PUBLIC de sa page (`acces`, `#lib/pages`) parmi
      ceux que sert `acces_menu` (`api/app/utils/acces_menu.py`, #2969) — `pageAuMenu` ;
      jamais un rôle ni un statut dans `Nav.svelte` (`npm run lint:manuel-menus`)
- [ ] Un geste d'écriture n'est offert qu'aux rôles que sa route accepte : le prédicat de
      l'écran n'est jamais plus large que la dépendance de la route (#2096). Un geste neuf se
      déclare dans `GESTES` de `test_ecran_offre_ce_que_la_route_permet.py`
- [ ] Ce que l'écran MONTRE est ce qui PART : une case ou une section rendue a son champ dans
      la charge, et un droit d'écran (`peutDiffuser`, `peutCibler`…) a un défaut **fermé**
      (#2142). Une case neuve se déclare dans `e2e/case-montree-charge-envoyee.spec.ts`
- [ ] Onglet réservé à un rôle : `reserve:` sur l'onglet dans `pages.ts`, jamais un masquage
      dans la page — `BarreOnglets` masque ET refuse la route directe (`npm run
      lint:onglets-reserves`)
- [ ] Nom affiché d'un objet « Saisi pour » : le champ servi `nom_proprietaire`, jamais
      `objet.auteur_nom` (le rédacteur) ; la case de copie dit `nomCopie` (`npm run
      lint:nom-proprietaire`)
- [ ] Section d'un formulaire : déclarée dans `#lib/entites/<entité>`, dans l'ordre de
      `SECTIONS_ORDRE` (`#lib/entites/types.ts` — la liste et son compte se lisent là,
      `npm run lint:consignes`) ; pliage *obligatoire → déplié · facultatif → plié*, ou son
      `exceptionPliage` (`npm run lint:etats`). Un composant qui porte une section la
      **transmet** (prop `pliable`, `npm run lint:pliage-transmis`), et l'appelant la passe,
      lue par `pliageDe` (#1329)
- [ ] Libellé qui NOMME un objet (bouton, titre de boîte, toast, confirmation) : le mot vient
      de `#lib/entites/<entité>` (`libelle`, `libelleNouveau`, `libelleModifier`). L'écran dit
      « Affaire » et « Actualité », jamais « Ticket » (`npm run lint:vocabulaire-ecran`)
- [ ] Séparateur (— · →) entre deux éléments : `{SEPARATEUR.point|tiret|fleche}`
      (`#lib/separateurs`) — sécable avant, insécable après ; jamais `{#if x}&nbsp;· …` ni
      `{a} · {b}` entre deux espaces sécables, sauf dans `<option>` et `<title>` (#2360, #2362,
      `npm run lint:espace-blocs`)
- [ ] Périmètre par défaut masqué : le badge passe par `BadgePerimetre` (`npm run
      lint:pictogrammes`)
- [ ] Archiver (pas supprimer) sur la vue principale — 📦, jamais un 🗑️ intitulé « Archiver » ;
      la corbeille ne s'offre qu'aux Archives (`test_suppression_aux_archives.py` : une carte
      qui archive s'y ajoute) ; le titre des archives vient d'une constante (`npm run
      lint:archives`)
- [ ] Champ requis : `<EtoileRequis vide={!champ} />`, collée au libellé, rouge tant que le
      champ est vide (#1121) ; une valeur par défaut active (« Tous ») la rend noire
      (`e2e/etoile-valeur-defaut`) ; un groupe : `<LibelleGroupe titre="…" requis vide={…}>`,
      jamais `titre="… *"`. Libellés en MAJUSCULES par le style (`champs.css`), jamais tapés
      (`npm run lint:champs`)
- [ ] Valeur d'une énumération (statut, type, catégorie, rôle) rendue par son LIBELLÉ, même
      derrière `?? '—'` ou dans un champ composé (`lot_type`, `type_lien`, `user_statut`) ;
      le lien d'un compte à un lot : `#lib/liens-lot` ; un champ qui porte déjà le libellé
      servi se déclare dans `EXCEPTIONS` (`npm run lint:categorie-brute`)
- [ ] Libellés en français — les mots d'interface anglais sont refusés par `npm run
      lint:vocabulaire-ecran` (`lib-mots-anglais.mjs`) ; le reste de la langue n'est pas
      mesuré
- [ ] Teinte choisie par donnée : `'var(--fil-rouge)'`, `--teinte-N`, `--kanban-…` — jamais
      un `#rrggbb` dans un `.ts` ou un script de composant (`npm run lint:couleurs-ts`) ; la
      valeur vit dans `socle.css`
- [ ] Couleur et taille : `var(--color-…)`, `var(--fs-…)` (`socle.css`), jamais en dur — à
      **zéro** pour les deux (`npm run lint:charte-valeurs`) : une couleur neuve est un jeton
      nommé par l'usage, une taille prend le cran de ce que l'élément EST (hors échelle → cran
      supérieur) ; un état prend son jeton et ses dérivés `-fond`, `-bordure` ;
      `--color-warning` ne sert jamais au texte (`--color-warning-texte`) ; une valeur égale à
      un jeton est refusée aussi (§18)
- [ ] Thème sombre : un jeton neuf a sa valeur dans `styles/palette-sombre.css` ou se déclare
      identique, avec sa raison ; aucun écran n'écrit `prefers-color-scheme` ni `data-theme`
      (`npm run lint:palette-sombre`, paires texte/fond AA). Contour d'un champ :
      `--color-border-champ` ; texte sur l'or : `--color-sur-accent`. Un aperçu imprimé ou
      envoyé reste clair : `class="ilot-clair"` (`npm run lint:ilots-clairs`). Le thème choisi
      ne se décide qu'à `#lib/theme.ts` et ne se choisit qu'au Profil (`ChoixTheme`,
      `e2e/bascule-theme.spec.ts`)
- [ ] Style dans le `<style>` du composant ou `src/styles/`, jamais en attribut `style="…"`
      sauf une valeur tirée des données (`width:{opt.part}%`, une part servie par l'API) — plafond zéro (`npm run
      lint:styles-en-ligne`). Si une règle globale plus forte vise l'élément, qualifier le
      sélecteur
- [ ] Bloc pliable : un seul déplié à la fois, par `#lib/accordeon`, jamais un `Set`
      d'ouverture ; exceptions arbitrées : section modifiée, carte en correction (`npm run
      lint:accordeon`)
- [ ] Rangée de pastilles qui FILTRE : `compte={<liste affichée>.length}`, montré sur la
      pastille retenue seulement (§5, `npm run lint:compte-filtres`)
- [ ] Recherche : `<ChampRecherche dans="…">`, jamais un `<input type="search">` ; la règle
      d'une liste reçue : `contientTousLesMots` (`#lib/texte`), sans accents (`npm run
      lint:recherche`)
- [ ] Attente : `<EtatListe chargement />`, jamais un « Chargement… » à la main (`npm run
      lint:chargement`)
- [ ] En-tête de page : `<EntetePage>`, jamais `<div class="page-header">` (§13)
- [ ] En-tête d'un écran sans session : `<EnteteAuthentification sousTitre="…" />`, jamais
      `auth-header` ni un émoji (`npm run lint:entete-auth`)
- [ ] Bouton d'action icône : `<IconeAction icone="…" />`, au trait — jamais un émoji. Une
      liste en cartes prend `Gouttiere` et `ReglagesListe` (§3, `npm run lint:actions-au-trait`)
- [ ] Bouton qui lance l'assistant IA : `<IconeIA {enCours} />`, le bouton portant
      `aria-busy={enCours}` ; ✨ ne se dit que de l'IA (`npm run lint:geste-ia`)
- [ ] Badge teinté par une table : `<Badge teinte={…}>`, jamais `class="badge {…}"` (`npm run
      lint:badge`)
- [ ] Icône vérifiée dans `#lib/icones-svg.json` (`npm run lint:icones` ; un relais d'icône
      s'appelle `icone`)
- [ ] Tout champ libellé dans un `.field`, y compris celui dont l'intitulé de section est le
      libellé ; une étoile dans un `label.field` enveloppant se tient dans un `<span>` avec son
      texte (#1230, `npm run lint:champs`)
