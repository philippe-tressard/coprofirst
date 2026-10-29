---
name: ux-patterns
description: "Apply and enforce 5Hostachy UX patterns: expand cards, tabs, pills, badges, photo thumbnails and galleries, kanban column visibility, pagination, accessibility, archiving, perimeter display, urgency, pinned items, form field conventions. Use when: implementing a new UI feature, reviewing UX consistency, checking if a pattern is correctly applied across all pages."
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


## 0. LE CADRE — une entité, quatre rendus (décidé le 17/08/2026)

**C'est la règle qui gouverne toutes les suivantes.** Les sections §9, §10, §13 et
§14 de cette skill en sont les instanciations ; en cas de désaccord, le cadre tranche.

> 📐 **Le cadre et sa maquette** : https://claude.ai/code/artifact/ed8e5dd8-67f0-4fd3-a0bc-e80653bac686
> 📊 **Le relevé des 42 couples menu/entité qui le fonde** : https://claude.ai/code/artifact/88087a21-8fe3-4463-8a35-a39f3032e5f3
> 🧠 **Le pourquoi, avec ses contre-exemples chiffrés** : mémoire projet
> `project_cadre_quatre_rendus` · 🎫 **#430**, lots #431 → #433 → #432

### Les quatre états

**Affichage** · **Création** · **Édition** · **Évolution** (une entrée de
**l'Historique**). « Commentaire » est abandonné : trop étroit, l'entrée pouvant
porter un changement d'état, des pièces jointes et une diffusion. C'est déjà le
vocabulaire du code (`TicketEvolution`, `EvolForm`).
⚠️ Le cadre parle d'évolutions ; **l'écran parle de gestes** — « Ajouter une
suite » (`#lib/gestes.ts`, depuis la v2.7.0 ; « Commenter » est le mot abandonné).

### Les sections, dans cet ordre — il ne se discute pas

L'ordre, les libellés **et le nombre** se lisent dans `front/src/lib/entites/types.ts`
(`SECTIONS_ORDRE`, `SECTIONS_LIBELLE`), et **nulle part ailleurs** : cette skill en
tenait une copie, qui plaçait encore « Mise en avant » avant « Destinataires » le
23/09/2026, jour où l'utilisateur les a inversées (#1096 : « elles sont
complémentaires »). `lint:ordre-sections` et `lint:etats` tiennent l'ordre.

🔴 Le **compte** se recopiait encore après la liste : ce titre annonçait
« treize » six jours après l'entrée de la quatorzième (#1342), comme
CLAUDE.md (#1541). `npm run lint:consignes` refuse désormais un nombre de
sections écrit dans une consigne — juste ou faux, il se périme.

Deux voisines à ne pas confondre : **Destinataires** = qui est concerné *dans
l'application* ; **Diffusion** = par quels canaux on prévient *à l'extérieur*.

🔴 **Le cadre recomposé le 21/09/2026 (#1095).** Trois changements, et un seul
touche un rang existant :

| | |
|---|---|
| **« Champs spécifiques » est SCINDÉE** | en *Nature*, *Au nom de* et *Mise en avant*. Elle portait trois intitulés sous un seul nom, ce qui rendait **indéclarable** une divergence ne concernant qu'un des trois — le cadre ne déclare que par SECTION. C'est la limite que #436 décrivait, et `ticket.ts` la portait en commentaire, invisible à `lint:etats`. |
| **Trois sections entrent** | *Équipement*, *Intervenant* (tous deux réservés aux catégories du bâti) et *Suivi* — qui est l'ancien *Workflow*, renommé. |
| **« Périmètre » remonte** | désormais **avant la Description** et dépliée. C'est le seul rang qui bouge, et il a été demandé : *« il a fallu plusieurs semaines pour l'UX de Périmètre, ne le casse pas »*.<br>⚠️ Elle s'est appelée **« Qui le voit »** le temps d'un lot, et l'arbitrage du 21/09/2026 l'a défait : *« Qui le voit est une CONSÉQUENCE, la section est Périmètre »*. Un intitulé qui décrit l'effet d'un champ plutôt que le champ lui-même vieillit mal — l'effet change, le champ reste. |

⚠️ **Destinataires passe donc après Description**, ce que la phrase « aucune
section existante ne change de rang relatif » du ticket ne disait pas. C'est le
tableau du ticket qui faisait foi : il était la spécification, la phrase en était
le résumé.

### Le PLIAGE — un troisième état de présence (#1095)

| État | Rendu |
|---|---|
| **Présente** | dépliée |
| **Pliée** 🆕 | intitulé + résumé d'une ligne, cliquable |
| **Absente** | rien, avec son motif |

Ce n'est **pas** une fusion : chaque section garde son intitulé, son rang et sa
déclaration. La règle est **calculée**, donc un pliage conforme n'a rien à
écrire :

```
obligatoire → déplié   ·   facultatif → plié
```

🔴 Un pliage qui s'en écarte exige `exceptionPliage`, et `lint:etats` refuse
dans les **deux sens** — une exception qui ne sert plus est aussi grave qu'une
exception qui manque. C'est ainsi qu'une liste de justifications devient une
liste de passe-droits.

Les trois arbitrées le 20/09/2026 : **Au nom de** (obligatoire mais pliée, le
défaut étant juste presque toujours), **Pièces jointes** (facultative mais
dépliée — premier geste sur téléphone). « Destinataires » devait être la
troisième : le contrôle a montré qu'elle n'est pas déclarée `requis`, donc son
pliage SUIT la règle et n'a rien à justifier.

⚠️ **Et toujours : une valeur autre que le défaut rouvre la section d'office.**
Cette partie-là n'est pas déclarative — elle dépend de ce que l'objet PORTE.
Une section pliée qui cacherait une valeur saisie serait pire que pas de pliage
du tout.

### Le quatrième motif d'absence : `categorie` (#1095)

`nature` (l'objet ne porte pas la notion) · `geste` · `hérité` · **`categorie`**
🆕 (la catégorie de l'objet ne l'appelle pas — l'Équipement et l'Intervenant ne
concernent que le bâti) · `api` (🔴 **dette, jamais un choix**, et doit citer un
ticket).

🔴 **Une section ne se fusionne pas TOUTE SEULE.** Autant de sections déclarées
que de sections rendues — même voisines, même courtes, même héritées. Ce qui est
interdit, c'est la fusion **à l'écran** de ce que la table sépare : elle crée une
section que rien ne déclare, donc que rien ne contrôle.

⚠️ **Photos et Documents ÉTAIENT deux sections.** Cette clause disait, en rouge et
depuis le 17/08/2026, qu'elles ne fusionneraient jamais. **L'utilisateur a
tranché l'inverse le 20/09/2026** (#1095) : une seule section, photos et/ou
documents — et le champ **nom affiché** vaut désormais pour une photo comme pour
un PDF.

🔴 Ce n'est pas la règle qui s'assouplit, c'est la **table** qui a changé. La
clause a été réécrite dans le lot même qui change la décision : laissée en
arrière, elle réclamerait la séparation qu'on vient d'abandonner, et quelqu'un la
rétablirait de bonne foi — exactement ce qu'a fait « Claude s'arrête au push sur
dev », restée fausse des semaines.

⚠️ **Une section, deux réservoirs** : le modèle distingue `photos_urls` (des URLs)
des `Document` (des entités avec un identifiant), et la fusion ne touche pas au
modèle. Ce qui s'uniformise est la SECTION.

### 🔒 Une section INACTIVE — le formulaire unique d'une affaire (23/09/2026)

Arbitré à l'écran, maquette à l'appui : *« un seul “+ Nouvelle affaire”… selon
la catégorie, les sections peuvent changer — grisées, pliées, inactives et sans
données pour celles inappropriées »*. Une actualité est une affaire de catégorie
**Actualité** ; elle se crée et se corrige dans `FormulaireTicket`.

- Une section qui ne s'applique pas à la **nature** choisie reste **à son rang**,
  titre atténué précédé de 🔒, pastille grise « sans objet » à la place du
  résumé, et son **motif écrit** en petite ligne dessous (au doigt il n'y a pas
  de survol). Style « A », arbitré sur captures le 23/09/2026 — les hachures du
  premier jet ont été refusées. Elle ne se déplie pas et son contenu n'est pas rendu.
- Le motif se **déclare** : `inactivePour` sur la section, dans
  `#lib/entites/<entité>` ; `motifInactif()` le lit. Jamais un `{#if}` d'écran.
- « Sans données » : ce qu'une section éteinte portait **ne part pas**
  (`#lib/formulaire-affaire.chargeUtileAffaire`). Changer de nature en correction
  l'**efface**, après une confirmation qui dit quoi (`pertesAuChangement`).
- La pastille qui ouvre l'autre chemin (« 📰 Actualité — Information, sans
  suivi ») est **en tête**, pleine ligne, bord « information » sur fond blanc (un fond bleu la faisait croire cochée), suivie d'un filet
  (`enTete` dans `CATEGORIES_TICKET`, variante A). Il n'y a plus de filtre
  par catégorie (§5 bis) : elle se filtre par sa **nature**.

### Un champ n'est pas un geste — d'où la seule différence création/édition

Les sections **1 à 8 décrivent l'entité** ; la **9 est un acte**.

| État | Contenu |
|---|---|
| Affichage | 1→8 en lecture · 9 absente |
| Création | 1→9 en saisie |
| **Édition** | **1→9 identiques à la création** — la Diffusion y est **rouverte** (18/08), mais **seule la transition décoché → coché envoie** |
| **Évolution** | **création sans le titre** (hérité) · workflow **tracé** · périmètre et destinataires hérités · **9 rejouable** |

🔒 **La Suite suit le MÊME ordre** (#1326, 25/09/2026, signalé à l'écran) :
`EvolForm` offre trois créneaux, rendus à leur rang — `avant_suivi` (Équipement),
`specifiques` (Quand, Intervenant), `mise_en_avant` (après les Destinataires) —,
déduits de `SECTIONS_ORDRE` (`#lib/evolutions.creneauDe`). Il n'en avait qu'un,
et la Mise en avant y passait avant le Périmètre. `lint:ordre-sections` tient
l'ordre dans `EvolForm`, `test_creneaux_suite.py` le créneau chez chaque hôte.

**L'édition corrige** — une erreur, un oubli, un complément. Le `PATCH` écrit une
**correction**, jamais une transition.

🔄 **La correction d'une SUITE rouvre toutes ses sections, Suivi compris** (arbitré
le 01/10/2026 : *« l'édition d'une suite doit permettre de modifier toutes les
sections éditables et surtout le suivi »*). Elle corrige **l'entrée**, à sa date —
jamais une étape de plus — ; reprendre l'état d'avant (`statut_avant`, calculé par
le serveur) en refait un commentaire, et l'affaire ne suit que si c'est sa dernière
transition (`api/app/utils/suivi_fil.py`). **Sans Diffusion** : la Suite est déjà
partie. Un seul montage pour la Suite et sa correction, sur les trois cartes —
`SuiteAffaire` ; côté serveur, `routers/tickets/suite_sections.py` sert l'ajout ET
la correction. 🔒 `test_correction_suite.py`, `e2e/correction-suite.spec.ts`.

🔴 **La Diffusion a rouvert à l'édition le 18/08/2026**, sur arbitrage : *le CS
doit pouvoir décider d'envoyer au syndic un objet déjà saisi*. Ce qui rend la
réouverture sûre n'est **pas** l'interface mais le **serveur** — seule la
transition *décoché → coché* envoie. Un canal déjà coché ne repart pas à chaque
enregistrement, donc corriger une faute de frappe reste silencieux.

⚠️ **Sans ce mécanisme, rouvrir est PIRE que fermer** : le `PATCH` stockerait le
drapeau sans rien envoyer, et la case promettrait un envoi qui n'a pas lieu.
**Avant de rouvrir un champ dans l'interface, vérifier que le serveur le
CONSOMME.**

### Les six règles

- **R1** squelette de page immuable (titre + action primaire en haut · corps ·
  soumission en bas à droite) — **et c'est LUI qui porte la responsivité**, une
  seule fois pour toutes les pages.
- **R2** ordre des sections (`SECTIONS_ORDRE`) immuable, **et valable pour l'affichage**.
- **R3** un champ est un **objet** à trois rendus, qui se rend **toujours pareil**,
  avec **le même libellé partout**, le requis marqué par **`*` et rien d'autre**
  (jamais « (optionnel) »), **le fond de saisie** s'il est éditable — le mode se lit
  alors sans lire un badge — et **toute sélection en pastilles arrondies, jamais un
  `<select>` nu**. Une pastille qui se déplie porte un **chevron `›`**, seule marque
  du second niveau, *qui annonce sans imposer*. **La hiérarchie est une DONNÉE**
  (`parent` + `selectionnable`), administrée dans Admin → Patrimoine :
  *« sans inventer de niveau dans les données »*.
- **R3 bis** une **rubrique** groupe des objets et porte leur ordre, agencement et
  allure — variantes **limitées et justifiées**. *Une variante ajoutée pour
  accueillir un écart existant ne factorise pas : elle entérine.*
- 🔴 **R4** toute divergence entre états **se déclare avec son motif** :
  **`geste`** · **`hérité`** · **`api`** ⚠️ *motif de dette, qui doit citer un
  ticket*. **Une divergence sans motif est refusée par la CI** (`lint:etats`).
- 🔴 **R5** l'**enrichissement se propage** (squelette → toutes les pages ; rubrique
  → toutes les pages hôtes ; objet → toutes les sections). **Donc il se propose sur
  UN écran, se fait constater, puis se généralise.** Jamais l'inverse.

### Où le cadre VIT dans le code (depuis #431, 17/08/2026)

| Quoi | Où | À faire avant d'écrire un écran |
|---|---|---|
| Les sections, leur ordre, leurs libellés, les états, les motifs | `front/src/lib/entites/types.ts` | ne jamais recopier cette table — ni son **compte** : cette ligne a dit « 10 » jusqu'au 27/09/2026, et la skill « treize » jusqu'au 02/10 (#1541) |
| La déclaration d'une entité et **ses divergences motivées** | `front/src/lib/entites/<entite>.ts` | la lire ; si elle n'existe pas, l'écrire |
| Le squelette de **lecture** (R1 pour l'affichage) | `FicheLecture.svelte` | l'affichage passe par lui, il tient l'ordre |
| Le squelette de **saisie** | `FormulaireCreation.svelte` + `ChampsCommuns.svelte` | les sections qu'il porte, jamais réécrites — leur rang se lit dans `SECTIONS_ORDRE` |
| La rubrique **Historique** (le fil) | `RubriqueHistorique.svelte` | **6 recopies sur 6 remplacées** |
| L'**en-tête d'une carte de liste** | `EnteteCarte.svelte` | titre / tags · date · actions — voir §3 |
| La rangée d'**états en pastilles** | `WorkflowPastilles.svelte` | jamais un `<select>` nu (R3) |
| **Toute** pastille de sélection | `Pastille.svelte` | jamais un `<button class="pill">` — voir le seuil ci-dessous |
| Le garde-fou R4 | `npm run lint:etats` | il refuse une divergence sans motif, un motif `api` sans ticket, **une section rendue hors déclaration**, et un intitulé absent de la déclaration — `SectionTitre` et `SectionDescription` compris depuis le 27/09/2026 (la FAQ, déclarée ce jour-là, l'a révélé) |

### Le seuil des listes courtes : **6** (arbitré le 29/08/2026, #491)

Une liste de **6 entrées ou moins** qui fait CHOISIR se rend en pastilles
(`Pastille.svelte`). Au-delà, elle reste ce qu'elle est.

🔴 **Filtres ET champs de formulaire** (arbitré le 26/09/2026, #1329, capture à
l'appui : « toutes en pastilles »). Le Type d'une annonce était une liste
déroulante de trois valeurs juste sous le filtre qui propose les mêmes trois
valeurs en pastilles. Dans un formulaire : `ChoixPastilles` avec `libelleVisible`,
`radio` pour un choix obligatoire, `tous="Aucune"` (ou « Inchangé ») pour
l'option vide, `defilante={false}`. Une liste construite à la volée (lots,
résidents) garde sa liste déroulante : sa taille ne se lit pas dans le code.

Le chiffre n'est pas arbitraire : les usages existants allaient de 2 à 6, et deux
cas se posaient juste au-dessus — `CATEGORIES_ANNONCE` (9) et les statuts
utilisateur (7). Le seuil les exclut, et il est **écrit ici pour que la question
ne se repose pas à chaque écran** : c'est en y répondant au cas par cas qu'on a
obtenu sept pastilles réécrites à la main.

🔒 **Garde-fou depuis le 06/09/2026 : `npm run lint:seuil-listes`.** La règle
existait depuis huit jours et **n'avait pas été appliquée** au filtre « type » des
petites annonces — trois valeurs en `<select>`. Personne ne l'a vu : une règle
écrite dans une skill ne se relit pas avant de toucher un écran qu'on croit sans
rapport. Même motif que `EnteteCarte`, `ChoixPastilles` et
`parse_json_perimetres` : le composant existait, la règle existait, et rien ne
les faisait appliquer.

⚠️ L'utilisateur a énoncé « **≤ 5** » le 06/09/2026. Les deux valeurs donnent le
**même verdict** sur tout le produit — aucune liste n'a cinq ni six entrées : 3
(types d'annonce), 3 (tri), 4 (états d'idée), 4 (états de ticket), 9 (catégories
d'annonce). Le seuil de 6 est conservé avec sa justification d'origine ; le noter
évite qu'on croie à une divergence, et rappelle que le chiffre exact importe
moins que le fait qu'il soit **écrit une fois**.

⚠️ **Deux formes voisines sur une même barre ne sont pas une incohérence** : les
annonces portent des pastilles (3 types) à côté d'une liste (9 catégories).
C'est la **cardinalité** qui choisit, pas l'écran — sinon la question se repose à
chaque barre, et c'est ainsi qu'on a obtenu trois formes pour la même intention.

🔴 **Mais au-delà du seuil, la liste a l'ALLURE d'une pastille** (24/09/2026,
arbitré avec l'utilisateur) : `PastilleDeroulante.svelte`, jamais un `<select>`
natif dans une barre de filtres. Le `<select>` d'origine — coins carrés, fond
gris, autre police, autre hauteur — « dénotait à côté du filtre ». Le composant
garde la liste NATIVE sous la pastille (roue du téléphone, clavier, lecteur
d'écran) ; un **filtre** se remplit en bleu dès qu'il filtre, comme une pastille
retenue ; un **tri** (prop `tri`) porte ⇅ et se cale à droite. `.filter-select`
n'existe plus.

⚠️ **Le tri est la seule exception au seuil** : trois valeurs, mais un ORDRE et
non un filtre — trois pastilles de tri à côté des pastilles de type se liraient
comme un seul filtre. Elle est **déclarée** par la prop `tri`, que
`lint:seuil-listes` lit : le contrôle mesure aussi `<PastilleDeroulante
options={CONSTANTE}>`, sans quoi il serait devenu aveugle le jour où le `{#each}`
est parti dans le composant.

⚠️ **Le seuil décide d'une CONVERSION, il n'impose pas de revenir en arrière.**
Les douze filtres d'équipement de `prestataires` restaient des pastilles — ils
ont cédé la place à une **recherche libre** le 28/09/2026 (demandé à l'écran),
le même `ChampRecherche` que la page Affaires ; un équipement se retrouve en le
tapant. Une barre à plusieurs groupes passe par `.filters--groupes`.

**Une pastille peut porter un SOUS-TEXTE** (`<span slot="detail">`), et c'est ce
qui a débloqué la conversion des listes qui portaient une description. Sans lui,
elles restaient en cartes maison — ou perdaient l'information.

🔴 Le cas qui l'a rendu nécessaire : les six types de prestataire portaient leur
description dans un `title`, donc **invisible au tactile** — un survol n'existe
pas sur téléphone, et c'est là que ces types sont le plus difficiles à
distinguer.

⚠️ **Ce qui NE se convertit PAS** : un vrai `radiogroup` avec des
`<input type="radio">`, comme les catégories de ticket. `Pastille` rend un
`<button>` : la navigation par flèches et l'annonce par le lecteur d'écran y
seraient perdues. L'uniformité ne se paie pas en accessibilité
(`standards/11-interface-et-ux.md` §2).

🔴 **La section 1 ne porte QUE le titre** (arbitré le 18/08/2026, sur les
Tickets où la catégorie était rendue *avant* lui). Ce qui qualifie l'objet —
catégorie, « Saisi pour » — est en **section 2**. Une section peut donc porter
**plusieurs champs nommés** : `titreEcran` accepte une liste, et `lint:etats`
continue de refuser un intitulé inventé sur place.

⚠️ **Limite connue de R4, trouvée le 18/08/2026** : elle ne déclare qu'une
divergence de **section**, pas de **champ**. Sur le ticket, la catégorie reste
ouverte en édition quand « Saisi pour » y est fermé (motif `api`, #431) — ce
motif ne peut pas s'écrire dans `absente` et vit en commentaire, **invisible au
contrôle**. Premier écart que le cadre ne tient pas.

🔴 **La présence d'une section ne se décide plus dans l'écran.** `avecPhotos`,
`avecDiffusion`… se gouvernent par `sectionPresente(ENTITE, etat, 'photos')` et
par rien d'autre. Une condition en dur (`{!modeEdition}`) rouvre exactement la
divergence silencieuse que le cadre supprime — et `lint:etats` la refuse.

✅ **`EvolForm` est gouverné par la déclaration** : il reçoit
`entite: EntiteDeclaree` (`EvolForm.svelte:116`). Ce paragraphe disait le
contraire — « pas encore gouverné », « sujet de #433 » — et c'est le genre de
mention qui survit le plus longtemps : elle décrit un travail **à faire**, donc
personne ne la relit le jour où il est fait.

### Ce que le cadre ne couvre pas

**Document** (1 champ commun sur 5 entre création et édition, *et c'est juste*),
**Utilisateur** (zéro champ commun), et **le moment du téléversement** — trois
régimes, dont un existe **pour raison de sécurité**, et qui **ne se voit pas à
l'écran**.

> ⚠️ Cette skill fait plus de 500 lignes. Le cadre y est **résumé, pas recopié** —
> le détail vit dans l'artefact et la mémoire. Prochaine évolution notable : la
> découper (§9 « Champs de formulaire » fait à lui seul 230 lignes).

## 0 bis. L'objet DOCUMENTS — un seul geste, sans exception (11/09/2026)

🔴 **Arbitré à l'écran, et posé comme standard sans exception.** Le dépôt d'un
fichier avait trois formes selon l'écran : les tickets employaient
`FichiersUpload` (pastilles horizontales, croix rouge), les actualités une liste
verticale avec un 🗑️ par ligne, les contrats une rangée composée sur place avec
leur propre champ « Titre ». *Le même objet ne peut pas avoir trois formes selon
l'écran qui le montre* — c'est R3 appliqué à la pièce jointe.

🔒 **Un seul sélecteur de fichiers : `FichiersUpload`** (27/09/2026, #1329). Le dernier
`<input type="file">` nu — `FormulaireDocument` : plans, règlement, CR d'AG,
diagnostics — est passé en mode `differe`. `npm run lint:fichiers` refuse le suivant ;
les gestes réellement différents (image unique remplacée sur place, import de
tableur, photo de la bannière) sont **déclarés** dans `SELECTEURS_NATIFS`, avec leur
raison. Au doigt, le bouton 📎 fait **44 px** (`pointer: coarse`) — il en faisait 22 ;
`e2e/depot-fichier.spec.ts` le mesure sur l'écran réel, API simulée.

### La forme, dans cet ordre exact

| # | Élément | Détail |
|---|---|---|
| 1 | **les pastilles des fichiers déjà joints** | en RANGÉE horizontale, elles passent à la ligne quand elles ne tiennent plus |
| 2 | **le bouton et le champ de libellé**, SUR LA MÊME LIGNE | le bouton d'abord — on choisit le fichier avant de le nommer ; le champ prend la moitié de la place restante, et son placeholder DIT ce qu'il fait : « Nom du document qui se substituera au nom du fichier (optionnel) » |
| 3 | **le compteur** `n/max · types acceptés` | sous la rangée : il commente ce qui a été déposé, il ne fait pas partie du geste |

⚠️ **Le bouton et le champ sont ALIGNÉS**, pas empilés : empilés, ils faisaient
trois lignes pour un seul geste, et le champ posé sous le compteur semblait
appartenir à autre chose.

⚠️ **Le bouton précède le champ**, et ce n'est pas un détail de goût : l'ordre
inverse faisait remplir un libellé avant de savoir ce qu'il nommerait.

⚠️ **Le champ de libellé n'a pas d'intitulé au-dessus.** Le placeholder dit à lui
seul ce que le champ attend et ce qu'il advient s'il reste vide ; un intitulé
« Libellé du document » par-dessus disait deux fois la même chose. Le nom
accessible est porté par `aria-label` — il ne coûte pas une ligne à l'écran.

### La pastille : « TYPE: nom »

`PastilleFichier.svelte`, et lui seul. Le **type** en tête, en majuscules et en
gris (`PDF`, `EXCEL`, `WORD`) ; le **nom sans son extension** ensuite — elle est
déjà dite par le type, et « PDF: contrat.pdf » allonge la pastille sans rien
apprendre ; une **croix rouge** pour retirer.

Le type se calcule dans `#lib/fichiers` (`typeFichier`, `nomSansExtension`),
jamais dans un écran : quatre rendus l'affichent, et un format recopié aurait
divergé au premier ajustement. Les familles bureautiques y sont ramenées au nom
que tout le monde emploie (`XLSX` et `XLS` → `EXCEL`), sinon deux tableurs
identiques portent deux étiquettes.

### Ce qui n'est PAS une exception

- Un écran qui manipule des **entités `Document`** (actualités) plutôt que des
  URLs (tickets) emploie la même pastille : c'est `PastilleFichier` qui accepte
  un `libelle` distinct du nom de fichier. La différence de modèle ne justifie
  pas une différence de rendu.
- Un écran dont le document devient un **vrai `Document` titré** (contrats)
  n'affiche pas un champ de titre à part : c'est le même champ de libellé, et
  c'est l'appelant qui décide ce qu'il en fait.

🔒 **Garde-fou : `npm run lint:fichiers`** refuse un champ de libellé de document
réécrit à côté du composant. Il ne voit pas tout — la disposition, elle, se
vérifie à l'écran.

### ⚠️ Où l'objet Documents se place

En **section « Pièces jointes »**, avec les photos — elles n'en font plus
qu'une depuis le 21/09/2026 (#1095). L'ordre des sections vaut pour cet
objet comme pour les autres : un dépôt de fichier correct dans une section mal
placée reste un écran faux.

🔴 Les deux contrôles restent distincts **à l'intérieur** de la section, parce
que le serveur distingue les deux réservoirs. Ce qui a fusionné est l'intitulé et
le rang, pas la donnée.

## 0 ter. Ce qui appartient à la LISTE reste au-dessus du formulaire (12/09/2026)

Signalé à l'écran sur les tickets : ouvrir « + Nouveau ticket » repoussait
l'**avertissement légal** et les **filtres** sous un formulaire d'une pleine
hauteur d'écran. L'avertissement sur les tickets d'urgence devenait donc
invisible au moment précis où l'on en crée un.

**L'ordre, sous le titre de page :**

1. ce qui **qualifie la liste** — un avertissement, un bandeau d'état ;
2. les **filtres** ;
3. le **formulaire de création**, quand il est ouvert ;
4. la **liste**.

⚠️ Ce n'est pas une préférence, c'est la règle la plus déployée : le
**calendrier** le fait déjà ainsi. Les tickets étaient l'écart, et l'écart n'était
visible que le formulaire ouvert — donc jamais pendant une relecture d'écran.

🔴 Ne pas confondre avec R1, qui place l'action PRIMAIRE en tête de page : c'est
le **bouton** qui reste en haut, pas la boîte qu'il ouvre. Le bouton s'efface
pendant la saisie (#367), le formulaire prend sa place dans le flux — après ce
qui qualifie la liste.

🔒 **Garde-fou depuis le 24/09/2026 : `npm run lint:filtre-avant-formulaire`.**
La règle était écrite ici depuis douze jours, et la Boîte à idées comme les Petites
annonces rendaient encore leur filtre SOUS la boîte ouverte (#1186) — signalé à
l'écran, jamais en relecture, puisque l'écart n'existe que le formulaire ouvert.

## 1. Icônes de contexte

| Icône | Signification | Usage |
|-------|--------------|-------|
| 📍 | Lieu physique (adresse, salle) | Texte inline, pas de badge |
| 🔹 | Périmètre logique (Parking, Bât.) | Badge — rendu par `BadgePerimetre` **seul** (§2) |

**Ne JAMAIS utiliser** 📍 pour un périmètre logique.

🔒 **`npm run lint:pictogrammes`** (#1045, 24/09/2026) : 🔹 ne se rend que par
`BadgePerimetre` ; une phrase qui nomme un périmètre (`LOSANGE`) et chaque vrai
lieu 📍 (`LIEUX`) se déclarent dans le contrôle, avec leur nombre d'occurrences.
Il a trouvé « 📍 Concerne votre bâtiment » (→ 🔹), « 📍 Dépannage » (→ 🔧) et un
badge recopié dans l'historique des annonces de hall.

## 2. Affichage du périmètre

**Il n'y a plus de table de libellés, ni ici ni dans le code.** L'arborescence vit
en base (table `perimetre`) et s'édite depuis `/admin/patrimoine` : le produit doit
servir une autre copropriété, qui n'a ni AFUL, ni quatre bâtiments, ni forcément de
caves.

> ⚠️ Cette section portait la table en dur — et elle en **omettait AFUL**, si bien
> qu'un développeur qui la suivait recopiait un défaut. C'est exactement ce que
> `standards/02` §2 décrit : une table recopiée finit par diverger, et la copie la
> plus consultée est celle qui trompe le plus longtemps.

**Écrire un code de périmètre est interdit** — `npm run lint:perimetres` échoue
dessus. Utiliser, depuis `#lib/perimetres` :

| Besoin | Fonction |
|---|---|
| libellé affichable | `perimetreLabel(items)` — accepte tableau **ou** chaîne CSV |
| « c'est le périmètre par défaut ? » | `estPerimetreParDefaut(items)` — **remplace** `=== 'résidence'` |
| valeur initiale d'un formulaire | `perimetreDefautListe()` |
| périmètre d'un bâtiment | `perimetreDuBatiment(batimentId)` |
| « concerne tout le monde ? » | `concerneTous(items)` |
| bâtiments visés | `batimentsCibles(items)` |

**Condition d'affichage** : ne jamais afficher le badge si `estPerimetreParDefaut()`
est vrai (c'est le défaut, le redire n'apprend rien).

### Comment un périmètre S'ÉCRIT — trois règles, portées par `perimetreLabel()`

1. **Un espace est qualifié par son parent** — « Bât. 3 › Toit », « AFUL › Voie
   d'accès ». Sans cela, le gabarit posant les mêmes neuf espaces sous chaque
   bâtiment, un ticket visant deux toits affichait « Toit · Toit » (18/08/2026).
   ⚠️ La qualification s'est arrêtée aux **bâtiments** pendant neuf jours, au motif
   que les enfants du parking ou des locaux techniques « portent déjà des libellés
   distincts ». C'était vrai du **seed**, pas de l'administration : une « Voie
   d'accès » créée sous AFUL s'affichait nue (27/08/2026). La condition porte
   désormais sur ce que le parent EST — une cible, ou un simple **regroupement**
   (« Bâtiments », `selectionnable = false`), qui lui ne préfixe jamais.
2. **Deux séparateurs, deux sens.** ` · ` sépare deux éléments ; ` — ` borne un
   groupe qui en contient plusieurs, et n'apparaît que là — sinon le « · » d'un
   groupe se confond avec celui qui sépare les groupes :
   `Bât. 4 › Logement · Jardin Bâtiment — AFUL › Voie d'accès`.
   Les deux constantes sont exportées (`SEPARATEUR_ELEMENT`, `SEPARATEUR_GROUPE`) —
   **les importer, jamais les retaper**, le sélecteur le fait.
3. **L'ordre affiché est celui de l'arbre, jamais celui des clics.** Le sélecteur
   stocke l'ordre de sélection ; `perimetreLabel()` trie et regroupe. Un rendu qui
   dépend du chemin de saisie n'est pas un rendu, c'est un hasard.

🔒 **Deux garde-fous en CI, tenus par la MÊME chaîne attendue** : la règle est
écrite deux fois (front et API — les contextes de build interdisent le partage), et
le 18/08 elle n'a été corrigée que d'un côté. `api/tests/test_perimetre_label_batiment.py`
exécute la forme serveur ; `npm run lint:libelle-perimetre` transpile et exécute la
forme front, puis vérifie que le test Python attend la même chaîne.

**Sélecteur** : `PerimetrePicker.svelte`, alimenté par le store — premier niveau de
pastilles, second niveau facultatif quand un bâtiment est choisi, et la
**description** du nœud affichée sous la sélection.

Rendu — l'icône du périmètre est **🔹**, jamais 📍 (cf. §1), et il s'écrit **une
seule fois** : `<BadgePerimetre perimetre={…} />` (prop `perimetre`, un code ou
une liste de codes ; `ton` en choisit la teinte). Le composant lit le libellé,
tait le périmètre par défaut et porte l'icône — aucune page ne compose son propre
`<span class="badge">` ni son `<p style="…">`. 🔒 `npm run lint:pictogrammes`
refuse le badge 🔹 écrit ailleurs, `lint:styles-en-ligne` l'attribut `style`.
Les trois rendus par page que cette section listait (actualités, calendrier,
tickets) sont tous passés par ce composant ; la page Calendrier n'existe plus
(#1092).

Le label vient de `perimetreLabel()` (`#lib/utils`) — ne pas réimplémenter la table
de correspondance dans une page.

## 2 bis. Les DESTINATAIRES — la nomenclature (arbitrée le 25/09/2026)

*« Tous les résidents était faux, car un copropriétaire bailleur ou un bailleur
n'est pas résident. »* Les libellés sont **au pluriel**.

| Libellé | Ce qu'il désigne | Statut serveur | Dans le code |
|---|---|---|---|
| **Tous** | aucune restriction de profil | tous | ✅ `LIBELLE_TOUS`, code `résidents` |
| **Copropriétaires occupants** | copropriétaires qui habitent leur lot | `copropriétaire_résident` | ✅ |
| **Copropriétaires bailleurs** | copropriétaires qui louent leur lot | `copropriétaire_bailleur` | ✅ libellé, code `bailleurs` |
| **Bailleurs** | louent **par délégation** d'un copropriétaire — ils ne lisent **pas** les affaires suivies (#1311) | `mandataire` (confirmé ; les **aidants** n'en sont pas, ils héritent du droit du copropriétaire qu'ils aident) | ✅ code `mandataires` (#1301, 26/09/2026) — `bailleurs` était déjà pris par le copropriétaire bailleur, et stocké |
| **Locataires** | locataires | `locataire` | ✅ |
| **CS** | le conseil syndical seul (confidentialité) | rôle `conseil_syndical` | ✅ pastille « CS » (lot 1) |

- Un **résident** HABITE la résidence : copropriétaire occupant **ou** locataire.
  Un copropriétaire bailleur, un bailleur **ne sont pas** des résidents.
- Le choix sans restriction s'écrit **« Tous »**, jamais « Tous les résidents » :
  `LIBELLE_TOUS` (`#lib/destinataires`), lu par le sélecteur, le badge d'état de
  la section et la pastille de lecture. Le **code** reste `résidents` — stocké en
  base, lu par `public_cible_visible` ; le renommer serait une migration.
- Le manuel suit (cartes d'écran « Tous »).
- La **pastille de lecture** — livrée au lot 1 (25/09/2026), maquette :
  https://claude.ai/artifact/WRVxXqqJaFATAmWfz7WTsn
  - calcul **unique** : `#lib/lecture` (`lectureDe`), appliqué à l'objet par
    `#lib/lecture-ticket` ; rendu `PastilleLecture` (carte) et badge d'état de
    `SectionDestinataires` (icônes par `ContenuBadge`). **Une** couleur, bleue ;
    rien sur la carte quand personne n'est exclu ; cadenas `lock` quand le
    périmètre est réservé ; « CS » remplace tout quand elle est confidentielle.
    Elle **remplace** les badges 🔒 et 🛡️ des cartes ; le 🔹 reste.
  - 🔴 le badge de la section lit la **même nature** que ses pastilles —
    catégorie et bâtiments compris (`...lecture`). Il ne recevait que
    `actualite` : sur une **Panne**, « Tous » était coché et le badge disait
    « Copropriétaires » (#1434, 28/09/2026). La règle pure était juste et
    éprouvée ; c'est son APPEL qui oubliait un argument —
    🔒 `e2e/destinataires-panne.spec.ts` compare le badge à la pastille cochée.
  - combinaisons nommées : **Résidents** (occupants + locataires),
    **Copropriétaires** (occupants + copropriétaires bailleurs) — c'est aussi
    la règle des affaires suivies, **montrée** (arbitré), depuis que les
    mandataires ne les lisent plus (#1311, 25/09/2026 : elle s'appelait « Tous
    sauf locataires », et « Propriétaires » côté actualités — un ensemble, un
    nom). Les autres se composent par « + » (court) et « et » (long).
  - au survol, la pastille entière porte la phrase complète (`title`) ; au
    doigt, c'est le toucher qui ouvre la bulle (#1311).
  - les deux cases qui restreignent ont **une** forme (case, icône du catalogue,
    libellé) et ouvrent leur section : « Réservé au périmètre sélectionné »
    (`lock`) en tête du Périmètre — cochée d'office pour une affaire —,
    « Confidentielle : le conseil syndical seulement » (`shield-check`) en tête
    des Destinataires, **affaires comprises**. Cela renverse le « sous les
    pastilles » de #1096. Elles ont quitté la Mise en avant (📌 🚨 seuls).
  - 🔒 **tenue contre le serveur** : `api/tests/donnees/lecture_pastille.json`,
    exécuté par `test_lecture_pastille.py` (règle) et `npm run lint:lecture`
    (résumé). Une règle d'accès qui change fait tomber les deux.
  - ✅ la pastille « Copropriétaires » a quitté le sélecteur (#1301, migration
    0221 : ses données portent désormais les deux codes). Le serveur et la
    pastille de lecture LISENT encore l'ancien code, aucun écran ne l'offre.
  - ✅ **lot 2** (26/09/2026) : « Bailleurs » (mandataires) est une pastille
    de Destinataires, code `mandataires`. La pastille « Conseil syndical »
    RESTE, arbitré à l'écran le même jour : « Résident concerné » se place
    entre Locataires et elle — trois degrés de restriction, pas un doublon.
  - ✅ **#1436** (28/09/2026) : CHAQUE catégorie d'affaire a ses Destinataires
    par défaut — la table vit au serveur (`DEFAUT_PAR_CATEGORIE`,
    `utils/visibility/defauts_affaire.py`), son miroir dans `#lib/lecture`, et
    `lecture_pastille.json` en tient un cas par catégorie. « Résident concerné »
    y est un DÉFAUT : la pastille est cochée sans poser le drapeau, et la
    vignette dit « Concerné ». Fermée ainsi, une affaire ne sort pas plus (groupe,
    hall) que cochée : une seule règle, `reservee_au_conseil`.

🔒 **Tenue depuis le 26/09/2026 (#1305) : `api/tests/test_libelle_tous.py`.** Il
refuse « tous les résidents » dans tout texte SERVI — littéraux Python hors
docstrings, balisage Svelte hors commentaires. Il a trouvé une cinquième
description (espaces verts) que le relevé à la main avait manquée. Les textes
déjà en base ont été remplacés par la migration 0226, à l'identique seulement.
Un périmètre à portée globale se dit « Visible de tous ».

## 3. Carte expansible (Expand Card)

**Le pattern principal** pour les listes (tickets, publications, événements, prestataires).

### 🔴 La structure d'en-tête — `EnteteCarte.svelte`, et elle vaut pour TOUT le site

Posée le **18/08/2026**, après un constat à l'écran : le titre partageait sa ligne
avec les tags, la date et les icônes, et **sur téléphone il disparaissait** — la
ligne étant en `flex` avec `text-overflow: ellipsis`, les badges de largeur fixe
gagnaient et le titre se réduisait à trois points. On lisait une liste sans savoir
de quoi elle parlait.

```
┌──────────────────────────────────────────────┐
│ Titre en gras               actions  ›       │
│ trois lignes d'aperçu                        │
│ tags ································ date   │
└──────────────────────────────────────────────┘
```

- le **titre**, en **gras** (600), tient la première ligne avec les **actions et
  le chevron** ancrés à droite ; il occupe tout le reste (2 lignes au maximum,
  puis coupé) ;
- puis l'**aperçu**, **trois** lignes (`.clamp-3`) ;
- **en dernier** : tags à gauche (workflow, périmètre, confidentiel, auteur),
  **date à droite**. Au bureau la ligne défile si elle déborde ; **au téléphone
  (≤ 767 px) elle passe à la ligne**, date alignée sur la dernière — la barre de
  défilement masquée cachait l'auteur (27/09/2026, arbitré à l'écran ;
  🔒 `e2e/ligne-pastilles.spec.ts`).
  🔒 **Toute la ligne est à UNE taille**, celle d'un `.badge` (0,75 rem), posée
  sur `.ec-tags` et héritée : état, périmètre, pastille de lecture, numéro,
  auteur. Ils en avaient quatre (#1308). `lint:entete-carte` refuse une autre
  taille sur un élément du slot `tags`, et `font: inherit`, qui réinitialise
  celle du badge.

🔴 **Cet ordre a été dicté à l'écran le 18/09/2026**, capture à l'appui : *« Titre
en gras (à gauche) et icônes à droite sur la 1ʳᵉ ligne · Description (extrait sur
4 lignes environ) · Pastilles en dernière ligne comme sur le fil d'actualité »*.
C'est le fil d'activité qui fait référence, comme pour le survol et le geste.

⚠️ L'aperçu passe donc **par `EnteteCarte`** (`slot="apercu"`), alors que chaque
carte le rendait après lui. Sans cela les tags ne peuvent pas descendre : l'aperçu
est un **frère** de l'en-tête, et aucun `order` CSS ne fait passer un élément sous
le frère d'un autre parent.

### 🔴 La densité — « F1 », validée à l'écran le 18/09/2026

> ⚠️ **Relâchée le 10/10/2026** (maquette B, puis #1819) : la forme AÉRÉE de la page
> Affaires est devenue la base de toutes les cartes — titre `--fs-lg`, aperçu `--fs-md`
> interligne 1,5, 0,85 rem entre deux cartes. Ce qui suit reste vrai pour le PRINCIPE
> (chaque bloc décide de son espacement ; le blanc venait des boutons), plus pour les chiffres.

Six essais ont été soumis avant celui-ci. Les chiffres ne sont pas décoratifs :

| | avant | F1 |
|---|---|---|
| hauteur d'une carte de ticket | 206 px | 110 px |
| blanc entre le titre et l'extrait | 13 px | 3 px |
| hauteur d'une fiche d'annuaire | 114 px | 62 px |

- l'extrait reprend la **typographie du fil** (`.flux-detail`) : gris, interligne
  **1,25**, marge entre paragraphes **0,12 em** — mais **0,75 rem** et non 0,8,
  parce qu'il vit sous un titre en gras, ce que le fil n'a pas : c'est l'ÉCART
  avec le titre qui fait ressortir le titre, et 0,8 rem n'en laissait que 2,1 px ;
- **aucun dégradé de fin** : le texte s'arrête net, comme dans le fil. Il y en
  avait un depuis le 15/08 pour dire « le texte continue », d'une hauteur FIXE
  de 2,2 em. L'aperçu étant passé de 5 lignes d'interligne 1,6 à 3 lignes
  d'interligne 1,25, il couvrait **59 %** du texte au lieu de 28 % — deux lignes
  sur trois, signalées à l'écran comme « un flou sur la 3ᵉ ligne ».
  ⚠️ Une valeur absolue dans un bloc dont la hauteur change reste juste jusqu'au
  jour où la densité bouge, et personne ne relit une règle qu'on n'a pas touchée ;
- `.entete` : `padding: .38rem .7rem .42rem`, `gap: 0` — chaque bloc décide de son
  propre espacement, un écart uniforme ne convenait à aucun des trois ;
- les cartes se suivent à **0,45 rem** (`.carte-liste`), plus 0,75.

🔴 **Les 13 px de blanc venaient des BOUTONS, pas des marges.** Un bouton
d'action fait 30 px de haut, un titre 19 : la ligne prend la hauteur du plus
grand, et la différence tombe sous le titre. On la cherchait dans les `margin`.
Les actions sont donc réduites à **22 px** dans l'en-tête — **sur grand écran
seulement** : sous 480 px la cible tactile reprend 32 px (`standards/11` §10), et
c'est alors le titre qui **se centre** sur elles. La piste des actions sorties du
flux (`position: absolute`) a été essayée et écartée : elle oblige le titre à leur
réserver une largeur fixe, dimensionnée pour la carte qui en porte le plus — une
fiche de membre, qui n'a que deux icônes, y perdait 12 rem de titre.

**Ne JAMAIS recomposer cet en-tête dans une page** : `EnteteCarte` le porte, avec
son style et son repli. C'est **R1** au sens propre — la responsivité appartient
au squelette, une seule fois pour toutes les pages ; chaque carte qui recomposait
son en-tête avait sa propre façon de mal se replier.

🔒 **Garde-fou depuis le 12/09/2026 : `npm run lint:entete-carte`.** Tout
fichier qui rend `.carte-liste` doit importer `EnteteCarte`. La liste
d'exceptions est **vide**, et c'est le bon moment pour l'ouvrir : le dépôt est
conforme. Une exception ajoutée devra dire pourquoi, et une qui ne sert plus
fait échouer le contrôle.

⚠️ **La règle était écrite ici depuis le 18/08 et DEUX cartes ne la suivaient
pas** — `CarteContrat` et `CartePrestataire` — pendant un mois, avec l'ancien
`role="button"` sur le conteneur et le chevron `▲/▼` que tout le reste du site
avait abandonné. Personne ne l'a vu, et la raison compte : **rien ne relit une
carte qu'on ne touche pas, et les deux étaient cohérentes ENTRE ELLES.** C'est
la forme la plus durable d'un écart — il faut une machine pour la voir. Même
famille que `lint:seuil-listes` (§0) : une règle écrite dans une skill ne se
relit pas avant de toucher un écran qu'on croit sans rapport.

**L'ORDRE DES ICÔNES est celui de la carte de ticket**, désignée comme référence :
**🔗 copier le lien · 🔄 commenter · ✏️ modifier · 🗑️ supprimer**, puis le chevron.
Il était inversé sur les actualités, et deux cartes du même site ne se lisaient pas
pareil.

🔴 **Et elles sont TOUTES dans l'en-tête — le 10/09/2026 l'a rappelé.** Sur la
carte d'un contrat, la corbeille était sur la ligne du titre et le crayon dans le
corps **déplié** : il fallait ouvrir un contrat pour découvrir qu'on pouvait le
modifier, alors que la suppression, elle, se voyait tout de suite. *Deux actions
du même objet, deux endroits, deux moments — et la plus destructive était la plus
accessible.*

⚠️ Corriger la FORME d'une action (bouton texte → icône) sans corriger sa PLACE
ne règle rien : c'est l'erreur commise le matin même, et signalée dans la foulée.
Les deux se vérifient ensemble.

🔴 **Le 🔗 est en PREMIER, et sa position est un raisonnement, pas un goût**
(05/09/2026). C'est la seule action que **tout le monde** a : posée entre ✏️ et 🗑️,
elle sauterait d'un cran selon les droits du lecteur, et deux personnes ne
verraient pas la même rangée au même endroit. Les trois autres sont conditionnelles,
elle non — donc elle est l'ancre.

**Il se rend par `BoutonLien.svelte`**, jamais à la main : il copie l'adresse
**absolue** de l'élément (`ancre="annonce-42"` → l'`id` que la carte pose déjà pour
les liens profonds, ou `chemin` quand la publication a sa page). Un lien relatif
collé dans un SMS ne mène nulle part, et le presse-papiers est refusé dans certains
navigateurs embarqués — le repli est dans le composant, une seule fois.

⚠️ **Copier un lien n'est pas un droit** : le composant se rend pour tout le monde.
Trois rangées d'actions étaient conditionnées au droit d'édition (FAQ, idées, et
la rangée du conseil syndical) — elles ont été ouvertes, l'édition restant, elle,
réservée. L'adresse ne donne aucun accès : la page vérifie les droits de qui
l'ouvre, pas de qui l'a envoyée.

### 🗂️ La carte d'AFFAIRE — gouttière datée (maquette B, 10/10/2026)

Demandé : une liste des affaires « plus premium et aérée, sans perdre aucune
information ». Arbitré à l'écran parmi cinq maquettes, d'abord **pour les affaires
seulement** (Liste et Archives).

🔴 **Renversé le soir même (10/10/2026), après livraison et vérification à l'écran** :
*« mémorise l'UX de la page Affaires : elle doit devenir un standard pour les autres
pages similaires »*. La page Affaires est la **référence** de toute page qui liste des
objets en cartes, avec recherche et filtres — Communauté (annonces, idées, sondages),
Prestataires & contrats, Espace CS, Documents… :

| Ce qui se reprend | La forme d'Affaires |
|---|---|
| la gouttière | la date de l'objet, puis ce qui le **classe** (nature, type, catégorie) — ce que l'objet n'a pas ne s'invente pas, la proposition le dit |
| les réglages | recherche en tête, filtres dessous, libellés alignés sur la gouttière (`--largeur-gouttiere`) ; compteur sur la pastille retenue seule (§5) |
| la carte | `EnteteCarte` (aérée), actions au trait (`IconeAction`), une seule date |
| la dernière ligne | capsules neutres pour ce qui décrit, teintées pour l'état et « qui la lit » |

🔴 **Généralisé à TOUT le site le 10/10/2026 au soir (#1819)** — *« l'UX (icônes,
cartes, tout l'UX) de la page Affaires est le standard pour le site. Applique-le à
toutes les pages, notamment Ma résidence, Prestataires, Contrats, Consommations, toute
la Communauté, FAQ, Espace CS, Admin »*, en respectant `emil-design-eng`. La règle
« une page à la fois » (R5) a cédé à cette demande explicite ; ce qui reste à
constater se demande à l'écran après livraison. Les briques ont pris le nom de la
NOTION, et la forme aérée est devenue la base :

| Brique | Ce qu'elle porte | Où |
|---|---|---|
| `CarteListe` | **le conteneur de toute carte de liste** (10/10/2026) : `.carte-liste`, la gouttière dès que `quand`, `classe` ou le créneau `gouttiere` la remplit (`.a-gouttiere`), le geste asymétrique (`onDeplier`, absent = la carte ne se déplie pas), ce qui l'ANNONCE (`onApprocher` : appui, survol à la souris, focus — précharger un corps différé, #1860), `expanded`, `urgent`, `archive`, `heure` (la gouttière dit l'heure, le jour étant l'intitulé du groupe) ; `class`, `style` et les `data-*` (teinte) sont transmis | toutes les cartes du site, **fil d'activité compris** (maquette B du fil, 10/10/2026 : heure puis rubrique, `classeFlux` ; la frise est partie — l'heure sous un intitulé de jour seulement : le bandeau Épinglé, qui n'en a pas, dit la date, 12/10/2026) ; 🔒 `npm run lint:carte-liste` refuse le conteneur, la gouttière ou un état de carte écrits ailleurs |
| `Gouttiere` | `quand` (ISO, découpé par `partiesDate`) puis `classe` (`{icone, libelle, abrege}`), et un slot libre dessous (le vote d'une idée) ; au téléphone (≤ 480 px), une ligne au-dessus du titre | rendue par `CarteListe` **seul** ; la carte **ne passe plus** `date` à `EnteteCarte` |
| `#lib/gouttiere` | le type `ClasseGouttiere` et `classeDe(table, marques, val)` : une notion déclare la **marque** de chaque valeur (`[icone, abrege]`), le libellé vient de sa table — `#lib/prestataires-gouttiere`, `classementAnnonce` | tout écran qui classe |
| `gouttiereAffaire(t)` | la gouttière d'une affaire, `{ quand, classe }` : `mis_a_jour_le ?? cree_le` et la nature (`natureDe`), à étaler sur `CarteListe` ; la teinte vient de `[data-nature]` (`--nature-fort`), sans elle le Bleu Seine | `CarteTicket`, `CarteActualite` (`#lib/tickets`) |
| `ReglagesListe` | la grille des réglages : libellés dans une colonne de la largeur de la gouttière, `ChampRecherche` **en tête**, puis `ChoixPastilles libelleDevant` / `FiltrePerimetre libelleDevant`, chacun avec `compte` | `FiltresAffaires` et toute page à réglages |
| `EnteteCarte` | la densité **aérée** est la base (l'ex-variante `ample`) : titre `--fs-lg`, aperçu `--fs-md` interligne 1,5, actions 26 px au bureau, 32 au doigt | toutes les cartes |
| `.carte-liste` | le filet sur trois côtés et 0,85 rem entre deux cartes (0,6 au téléphone) | `normes.css` |
| `IconeAction` | le pictogramme **au trait**, partout : gris `--color-text-muted`, Bleu Seine au survol ; plus de contexte de liste, plus d'émoji | tout bouton d'action icône ; 🔒 `npm run lint:actions-au-trait` |
| `IconeIA` | le geste qui lance l’assistant : ✨ au repos, ⏳ Bleu Seine qui clignote pendant l’appel — le bouton porte `aria-busy` (arbitrage n° 21) | tout bouton qui appelle l’IA ; 🔒 `npm run lint:geste-ia` |
| `.badge` | une **capsule** (coins de 6 px) sur tout le site ; `.badge-gray` neutre (pierre) sur la dernière ligne d'une carte (`.ec-tags`, `.pa`) | `composants.css` |

🔴 **Une carte archivée a UNE allure** (10/10/2026, `CarteListe archive`) : atténuée à 0,8, pleine une fois dépliée et au survol (au pointeur seulement). Il y en avait cinq — `.attenue` sous trois variantes, `.item-inactive` de la FAQ (0,55, jamais pleine), `.history-item` de l'affaire (liseré gris, sans le filet de la carte). Une classe passée par `class` vit dans `CarteListe` : le `<style>` de l'appelant ne l'atteint qu'en `:global(…)` — les teintes (`[data-nature]`, `[data-type-annonce]`) et les états vivent donc dans `normes.css`.

Ce qui n'a pas d'équivalent ne s'invente pas : une gouttière sans date ne porte que le
classement ; sans classement, que la date ; un objet sans l'un ni l'autre n'en a pas
(un membre de l'annuaire). Un **tableau** reste un tableau (Admin, Reporting) : il
prend les actions au trait et les capsules, pas la gouttière.

⚠️ Pas fait, et pourquoi : « NEW » n'est pas devenu « Nouveau » — `BadgeNouveau` porte
l'arbitrage du 26/09 (« le NEW rouge, partout »), qu'une maquette d'affaires ne défait pas.

### 🔴 La DERNIÈRE LIGNE d'une carte — `PastillesAffaire` (arbitré à l'écran le 27/09/2026)

La ligne de la carte d'**affaire** fait la norme. La carte d'**actualité** et le **fil
d'activité** la rendent **à l'identique** — mêmes pastilles, même couleur, même nom,
même place. Elles différaient sur neuf points (catégorie en texte, état absent du fil,
périmètre en tête, « urgent » rouge contre « ⚡ Urgente » orange, numéro en badge,
auteur sans ✍️, lecteurs et ✨ absents du fil…).

| # | Pastille | Forme |
|---|---|---|
| 1 | catégorie | **emoji seul**, libellé au survol |
| 2 | état | badge coloré — **absent sur une actualité sans suivi** ; le suivi optionnel d'une actualité (Ouvert · Résolu · Annulé, 10/10/2026) s'y montre (`etatAffiche`) |
| 3 | périmètre | `BadgePerimetre` (🔹, tu quand il vaut le défaut) |
| 4 | qui la lit | `PastilleLecture` (bleue, tue quand tout le monde lit) |
| 5 | urgence | « ⚡ Urgente », **orange** — le glyphe vient de `GLYPHE_URGENCE` |
| 6 | marqueurs | 📌 Épinglée… (`optionsEnBadge`) — **pas de 📌 dans le fil**, qui a son bandeau |
| 7 | numéro | `#TK-…` en texte simple, pas en badge |
| 8 | auteur | **« ✍️ Nom »**, texte discret — `AuteurCarte`, la seule écriture |
| 9 | IA | ✨ `MarqueIA`, juste après l'auteur |

Les **autres** cartes du fil (annonce, sondage, idée…) suivent le **même ordre** avec ce
qu'elles ont : état, 🔹, ✍️ auteur, ✨. Même **typographie** que `.ec-tags` (0,75 rem).

**Leurs cartes de liste** — `AnnonceCard`, `ListeIdees`, `ListeSondages` — aussi (#1373,
arbitré le 27/09/2026) : état · 🔹 (jamais teinté) · **qui la lit** · leurs pastilles
propres (prix, votants…) · ✍️ · ✨ en fin de ligne, plus à côté du titre.
- La **pastille de lecture** remplace le badge orange des destinataires :
  `<PastilleLecture cible={objet} />` (`masculin` pour un sondage). Leur règle est
  `cible_visible` — le périmètre restreint **toujours**, d'où le cadenas —, résumée par
  `lectureCiblee` et tenue par les cas `objet` de `lecture_pastille.json`.
- 🔴 L'auteur d'une **idée** ou d'un **sondage** n'est **jamais** affiché (arbitré le
  27/09/2026) : leurs API ne l'exposent pas, et l'exposer serait une décision de données
  personnelles. La petite annonce nomme le sien — le nom que l'API sert déjà.

🔴 **Le squelette de ce pied est `PiedCarte`** (24/10/2026, demandé à l'écran sur le carnet
d'entretien, où le n° TK avait sa propre ligne sous l'aperçu) : catégorie (emoji) · *créneau*
· `#numéro` · *créneau de fin* (✍️, ✨). `PastillesAffaire` et `CarnetEntretien` le montent, et
lui seul écrit l'emoji de catégorie et le numéro — une carte qui dit une affaire n'écrit pas
son pied, elle remplit ses créneaux. Le carnet y garde sa règle, la portée **toujours** dite,
par `<BadgePerimetre toujours />` : le même badge 🔹, qui ne tait plus le défaut.

🔒 `npm run lint:pastilles` (les trois cartes passent par `PastillesAffaire`, et le pied du carnet par `PiedCarte`, ✍️ ne
s'écrit que dans `AuteurCarte` ; les cartes de la communauté rendent `PastilleLecture`, sans 🔹
teinté ni ✨ avant elle, et l'idée comme le sondage sans auteur) · `e2e/ligne-pastilles.spec.ts` (le fil et la carte,
rendus avec la même affaire, lisent la même ligne) · `test_flux_pastilles.py` (le
serveur envoie la ligne au fil, et ✨ sur chaque carte de la communauté).

### 🗂️ L'affaire DÉPLIÉE au fil — la brique des trois étapes (n° 66, 18/10/2026, #2078)

Une même affaire dépliée avait deux rendus : la brique G dans la liste Affaires,
trois encarts (maquette A du 15/10, TK-109008) au fil. **Décidé : la brique G
partout** (`RubriqueEtape`, §3 n° 20), et le fil l'ouvre sur **« La suite »** —
il répond à « quoi de neuf » —, la liste sur « La demande ». Seule l'étape ouverte
par défaut change : titres, ordre, teintes et résumés sont ceux de la liste.

| Étape | Au fil | Forme |
|---|---|---|
| **La demande** | pliée, résumé « date » | la fiche, **ses** pièces |
| **La suite · n entrées** | **ouverte** : trois entrées, puis « plus anciennes » | chaque entrée porte **ses** pièces |
| **La synthèse** | pliée, en dernier, si l'affaire est close et la synthèse lisible | « Validée le … · affaire close en n j » |

- **Un seul composant** : `FluxAffaireEtapes` (le fil) charge l'affaire et son fil à
  l'ouverture (`tickets.get`, `tickets.evolutions`) puis rend `CorpsCarteTicket` — celui
  de la liste — avec `ouverteParDefaut="suite"`. Une affaire **sans suite** n'a que sa
  demande, dépliée : elle EST la nouvelle. Le corps est différé et préchargé à
  l'approche de la main (`chargerCorpsAffaire`, `affaire-au-fil.ts`, #1860).
- **Pourquoi à l'ouverture et pas dans la réponse du fil** : le fil ne porte que la
  dernière suite (`meta.evol_*`) ; trois entrées par carte alourdiraient la réponse que
  l'accueil lit entière. Aucun changement d'API.
- **Lecture seule** : `peutSuivre` faux, gestes inertes sauf `filChange` (un transfert
  défait, une synthèse produite se relisent). Corriger une suite se fait sur la page
  Affaires — « Voir l'affaire → ».
- 🔴 **La synthèse enrichit la carte, elle ne la date pas** (arbitré le 15/10/2026) :
  validée un ou deux jours après la clôture, une affaire qui remonterait en tête se
  lirait comme une nouvelle panne. La Suite `synthese` n'est pas une candidate du fil
  (`test_flux_affaire_rubriques.py`).
- L'état ne se redit pas dans le corps (« État : Résolu ») : il est dans la ligne de pastilles.
- 🔒 `e2e/fil-rubriques-affaire.spec.ts` : trois étapes au fil avec leurs pièces, une
  affaire neuve, et la **parité** — la même affaire lue au fil et dans la liste a les
  mêmes titres, ordre, teintes et résumés, l'ouverture par défaut étant la seule
  différence. `FluxRubriquesAffaire` est retiré ; `evol_pieces` et `demande.*` restent
  envoyés par le serveur (le marqueur d'affaire, et la compatibilité d'un onglet PWA
  resté sur l'ancienne version).

### La source unique : `.carte-liste` (`styles/composants.css`) — depuis le 15/08/2026

Le conteneur, son espacement, son survol et son état d'urgence vivent **une seule
fois**, dans `front/src/styles/composants.css`. Actualités et tickets les redéfinissaient chacun
de leur côté, avec les mêmes valeurs et un simple préfixe qui change — rien
n'empêchait la troisième copie.

```svelte
<div class="carte-liste pub-expand" class:expanded class:urgent={item.urgente}>
```

La page ne garde chez elle que ses **différences** (`.pub-expand.brouillon`,
`.tk-cat`…). Ne jamais y redéfinir marge, bordure gauche, rayon, fond ou ombre.

**Espacement** : `.75rem` entre deux cartes (`.6rem` sous 640 px). Il était de
`.3rem`, et l'aperçu tronqué **net** au ras du bord : deux cartes voisines
formaient un pavé continu où l'œil ne trouvait plus la limite. Signalé par
l'utilisateur, pas par un contrôle — aucun test ne dit qu'une liste est confuse.

**Fin d'aperçu** : `ApercuCarte.svelte` estompe la dernière ligne par un
dégradé, **et seulement si le texte déborde vraiment**. ⚠️ Appliqué sans
condition, il efface la dernière ligne d'un aperçu court et annonce une suite qui
n'existe pas — constaté à l'écran. Aucun sélecteur CSS ne sait dire « ce texte
déborde » : la mesure se fait après rendu (`scrollHeight > clientHeight`).

### Règles
- **Une seule** carte ouverte à la fois — et un seul bloc déplié, quel qu'il soit
  (arbitrage n° 17, `ARBITRAGES.md`, `#lib/accordeon`)
- Chargement lazy des détails au premier clic
- Une liste qui peut compter des dizaines de cartes se **rend par paquets** :
  `#lib/rendu-progressif` (`aRendre`, `quandProche`) — les premières d'emblée,
  la suite à l'approche du bas, la carte visée par un lien toujours rendue. Seul
  le rendu change : filtres et compteurs portent sur la liste entière (#1840,
  Affaires par `ListeTickets`)
- Prévisualisation `.clamp-3` (3 lignes max dans une carte, §7)
- Border-left, urgence, espacement et ombre : **portés par `.carte-liste`** (voir
  ci-dessus). Ne pas les redéfinir dans une page.
- Urgence : bord gauche rouge, et **un seul glyphe, ⚡** (27/09/2026, arbitré à l'écran) —
  la case, le bouton d'options, le bandeau, l'avertissement et le manuel disaient 🚨,
  la carte ⚡. Il s'écrit dans `OPTIONS_PUBLICATION` et se LIT ailleurs
  (`GLYPHE_URGENCE`) ; 🔒 `npm run lint:pictogrammes` refuse 🚨 partout, manuel compris.
  Une **affaire** en priorité haute porte en plus son badge de priorité, « ⚡ Urgente »
  (`PRIORITE_BREVE`), **une fois** : la rangée des options passe par `optionsEnBadge`
  (`#lib/tickets`), qui retire ce qu'un badge dédié dit déjà — urgence et
  confidentialité. Elle les répétait (27/09/2026, #1364). 🔒 `npm run lint:options-en-double`
- **Le corps déplié ne referme pas la carte** : `on:click|stopPropagation` dessus.
  On referme par l'en-tête. Sans cela, impossible de sélectionner du texte, et un
  clic sur une photo ou un formulaire referme ce qu'on lisait. Le fil des
  actualités était le seul à ne pas l'appliquer (corrigé le 15/08/2026, signalé
  par l'utilisateur — qui croyait l'anomalie du côté des tickets, alors que
  c'étaient eux qui avaient raison).
- **Aperçu replié : vignette dès que l'élément porte une photo**, via
  `ApercuCarte.svelte` (ou `FluxVignette` quand la carte n'a pas d'aperçu texte).
  Vaut pour **les six écrans dépliables**, vérifié un par un le 15/08/2026 : fil
  d'activité, actualités, tickets, espace CS, calendrier, prestataires. Les trois
  derniers ne l'appliquaient pas — et le **calendrier** laissait joindre des photos
  à un événement sans jamais les montrer, ni repliées ni dépliées.

  ⚠️ Deux architectures donnent le bon comportement de refermeture : conteneur
  cliquable **+** corps en `stopPropagation` (actualités, tickets, calendrier), ou
  en-tête cliquable **+** corps *frère* (prestataires). Ne pas « corriger » une
  absence de `stopPropagation` sans regarder la structure : on casserait ce qui
  marche.
- Accessibilité : `standards/11-interface-et-ux.md` §2 — mais le conteneur d'une carte est
  `role="presentation"` (le geste appartient au titre, voir plus haut)

### Préfixes par page
| Page | Préfixe CSS | Référence |
|------|------------|-----------|
| Actualités | `.pub-` | **`CarteActualite.svelte`**, rendue par `ActualiteEnListe` **dans la liste des affaires** |
| Affaires (tickets) | `.tk-` | `tickets/+page.svelte` → `ListeTickets` |
| Calendrier | — | plus une page (#1092, 23/09/2026) : filtre « Calendrier » et onglet Kanban d'Affaires |
| Tableau de bord | `.pub-`, `.ev-`, `.tk-` | `tableau-de-bord/+page.svelte` |

🔴 **Il n'y a plus de page Actualités** (23/09/2026, #1091 lot 4 et #1092) : une
actualité est une affaire de catégorie « Actualité », et `ListeTickets` choisit
sa carte — `ActualiteEnListe` (allure d'actualité, sans numéro ni état) ou
`CarteTicket`. Les deux reçoivent le **même** objet `gestes` : un geste propre à
l'actualité ne s'écrit pas à côté. Le filtre de la vue Affaires est
`OPTIONS_FILTRE_NATURE` (Actualité · Calendrier · Affaire — valeur `activite`, libellé renommé le 24/09/2026), lu sur
`Ticket.natures` que le serveur dérive — jamais redérivé à l'écran.
`/actualites` n'est plus qu'une redirection (anciens liens `#pub-N` compris).

⚠️ **La carte des actualités est un composant depuis le 15/08/2026** (#356) :
`CarteActualite.svelte` sert le fil **et** l'Historique, qui rendaient jusque-là
le même balisage deux fois — le lot #351 avait dû y appliquer quatre
modifications au lieu de deux. Toute évolution de la carte se fait là, une fois.

Le balisage part **avec ses règles CSS** : Svelte scope les styles au composant.
Ce qui reste dans la page (formulaires, fil d'évolutions) y est passé en **slots**
— écrit dans la page, donc stylé par la page. Le signal qui dit que le découpage
est correct est `svelte-check` : **aucun** « Unused CSS selector » nouveau.

### Le GESTE de dépliage — il est ASYMÉTRIQUE (18/08/2026)

```
carte REPLIÉE  → toute la zone déplie · le fond change au survol
carte DÉPLIÉE  → SEUL le titre replie · le corps se lit et se sélectionne
```

> ⚠️ **Périmé sur un point** : le fond ne change pas au survol, c'est le TITRE qui se
> colore — arbitrage n° 2 (`normes.css`, vérifié le 18/10/2026). Vaut aussi pour la
> ligne `styles/composants.css` du tableau ci-dessous.

Formulé ainsi : *« applique partout la logique du fil d'actualité : cliquable
sur toute la zone pour déplier, avec changement de couleur au survol »* puis
*« clic sur le titre seul pour le repliement — pour permettre de sélectionner le
texte sans le replier »*.

🔴 **L'asymétrie résout le conflit**, elle ne l'arbitre pas : une grande cible
pour ouvrir (au doigt, sur téléphone), aucune cible parasite une fois ouvert
(pour lire, sélectionner, copier). Les deux exigences ne se contredisent pas —
elles ne portent pas sur le même état.

⚠️ **Trois allers-retours dans la même journée** avant d'y arriver, parce que je
lisais chaque moitié de la règle sans l'autre : d'abord « le titre et lui seul »,
puis « toute la carte », enfin les deux à leur moment. La leçon n'est pas qu'il
fallait deviner — c'est qu'une objection juste dans l'absolu (« la carte entière
intercepte la sélection ») peut être **hors sujet** ici : le corps déplié arrête
déjà la propagation, et la zone repliée n'a rien à sélectionner.

**Mise en œuvre**, une seule fois :

| Où | Quoi |
|---|---|
| conteneur de la carte | `role="presentation"` + `on:click={() => { if (!expanded) basculer(); }}` |
| `EnteteCarte` | `basculable` → le titre devient un `<button>` qui bascule, avec `stopPropagation` |
| `styles/composants.css` | `.carte-liste:not(.expanded)` porte le curseur **et** le fond au survol |
| corps déplié | `.carte-corps` + `role="presentation"` + `on:click\|stopPropagation` |

⚠️ Le titre est un **vrai `<button>`** : il porte le clavier dans les deux sens.
Le conteneur n'est donc pas interactif, et rien n'est imbriqué.

⚠️ `:not(.expanded)` porte toute la règle de survol. Sans lui, le curseur
promettrait partout un clic qui ne fait rien, et le fond se surlignerait sous un
formulaire ouvert.

## 4. Onglets (Tabs)

### 🔴 UN ONGLET EST UNE ADRESSE (05/09/2026) — et la rangée est UN composant

Demandé par l'utilisateur : *« que chaque onglet et sous-onglet soient accessibles
directement par une URL »*, après avoir voulu envoyer une petite annonce et n'avoir
eu à copier que l'adresse de la page voisine.

| Ce qu'on écrit | Où |
|---|---|
| la rangée | **`BarreOnglets.svelte`** — `<BarreOnglets pageId="…" actif={onglet} />`, jamais un `<div class="tabs">` à la main |
| la liste, l'ordre, le libellé **et la route** de chaque onglet | `#lib/pages.ts` (`onglets[].route`, `onglets[].sous[]`) |
| la résolution route ⇄ onglet | `#lib/routes-onglets.ts` (`routeOnglet`, `ongletDepuisChemin`) |
| la lecture de l'URL | le **`load`** du `+page.ts` : `resoudreOnglet(pageId, url)` |
| l'onglet dans l'écran | `export let data` → `$: onglet = data.onglet` — **jamais** un `let onglet` qu'on affecte |

**La forme de l'adresse** : *plate quand l'onglet est un CONTENU* (`/annonces`,
`/idees`, `/sondages`), *imbriquée quand il est une VUE* (`/tickets/kanban`,
`/espace-cs/reporting`, `/mon-lot/location/archives`). `/kanban` seul ne dit pas de
quoi il parle.

**Mécanique SvelteKit** : **`reroute`** (`front/src/hooks.ts`) traduit l'adresse en
route avant que le routeur ne cherche le fichier — `/annonces` est rendue par
`routes/(app)/sondages/+page.svelte`, sans redirection, sans fichier dupliqué et
**sans déplacer un seul écran**. L'URL affichée ne change pas : c'est elle que reçoit
le `load`, et c'est elle qui dit l'onglet. Un chemin non déclaré n'est pas traduit,
donc SvelteKit rend une **404** — se replier sur le premier onglet ferait passer
`/calendrier/kanbna` pour une adresse valide, et le lien cassé survivrait.

⚠️ **Un segment de reste (`section/[...vue]/`) faisait la même chose et a été
abandonné** : il oblige à DÉPLACER l'écran, et le garde-fou de modularité compte
alors un fichier de 1 800 lignes comme un fichier neuf au-dessus du plafond. Le
contrôle avait raison sur le fond — un écran de cette taille doit être découpé —
mais pas au prix d'un refus de toute réorganisation d'URL. `reroute` ne touche à
aucun écran.

- Descriptif par onglet : rendu par `BarreOnglets`, plus par l'écran — et tu s'il
  répète celui de la page (§13, #1369)
- Un onglet fermé à un profil se **masque** **et** se **redirige** — masquer répond
  à ce qui s'AFFICHE, rediriger à ce qui s'ATTEINT, et `BarreOnglets` fait les deux.
  Deux façons de le lui dire, qui ne se confondent pas :
  - une exigence de **rôle** → `reserve: 'proprioOuCS' | 'nonLocataire'` **sur
    l'onglet**, dans `pages.ts`. C'est là que regarde celui qui ajoute un onglet ;
    la page n'a alors rien à porter. 🔒 `npm run lint:onglets-reserves` confronte
    chaque valeur à la dépendance d'auth du routeur qui la justifie ;
  - un masquage qui dépend des **données** → la prop `masques` de la page, seule à
    savoir (« Gestion locative » n'apparaît que si le lot a des baux).

  🔴 Ce n'était **que** `masques` jusqu'au 20/09/2026, et une page pouvait donc ne
  rien déclarer du tout : `/residence` rendait sa rangée sans masque, et l'onglet
  « Carnet d'entretien » s'affichait au locataire dont la route répond 403 (#1039).
  Rien ne pouvait le signaler — il n'existait aucun endroit où la réservation était
  *écrite*.
- **Ne jamais utiliser** le pattern `view-toggle` / `view-btn` (pattern non-standard, supprimé)

⚠️ `?onglet=` était la convention jusque-là. Les anciennes adresses partent en
**308** depuis `resoudreOnglet` — e-mails déjà envoyés, favoris et liens de l'API
continuent de fonctionner — mais **plus rien ne l'écrit**. Côté API, `EMPLACEMENTS`
(`app/utils/liens.py`) porte désormais des routes, et `test_liens_front.py` vérifie
qu'elles sont déclarées dans `pages.ts`.

Pages implémentées : `mon-lot`, Communauté (`/sondages` · `/idees` · `/annonces`),
`espace-cs`, `calendrier`, `prestataires`. **`admin` reste sur `?onglet=`** :
demande explicite de l'utilisateur (« sauf admin »). Ses onglets sont pourtant
DÉCLARÉS dans la table depuis le 01/10/2026 (route `/admin?onglet=<id>`, `groupe`)
et rendus par `BarreOnglets` : ils se renomment et se décrivent dans « Menu et
pages » comme les autres.

### 🔴 4 bis. L'onglet ACTIF se voit — trois marques, pas une

Arbitré à l'écran le 30/08/2026 : *« on ne voit pas l'onglet actif ; ajoute ce
design dans l'UX et applique-le à tous »*.

`.tab-btn.active` (`styles/ecrans.css`) porte les **trois** marques, et il les
faut toutes :

⚠️ **Il y a DEUX sélecteurs, et c'est ce qui a coûté une marque.** `.tabs
button.active` habille les onglets-boutons, `.tab-btn.active` les onglets-liens —
et seul le premier portait la graisse. Tant que les onglets d'un écran étaient des
`<button>`, personne ne le voyait ; le jour où ils ont eu une adresse (05/09/2026),
toutes les rangées du site sont passées par le second. Corrigé le même jour.

| Marque | Pourquoi elle ne suffit pas seule |
|---|---|
| **liseré bas** en couleur primaire | la seule qui se voie d'un coup d'œil — c'est celle qui manquait |
| **couleur** du texte en primaire | seule, elle se confond avec le survol |
| **graisse 600** | seule, elle est trop discrète ; et elle porte l'écart pour qui distingue mal les couleurs |

**Un écran ne redéfinit JAMAIS `.tabs button` en entier.** Il ne pose que son
écart — taille, espacement, icône — et hérite du reste.

⚠️ **Le défaut, et il est structurel.** `prestataires` redéfinissait les neuf
propriétés de la charte, dont `color` et `border-bottom: transparent` : les deux
que `.active` change. À spécificité égale, le style **scopé** d'un composant
Svelte est injecté APRÈS la feuille commune — il gagne. Le liseré de l'onglet
actif disparaissait donc, sans qu'aucune règle ne soit fausse.

🔴 Et un commentaire posé juste à côté affirmait *« cet écran ne garde que son
ÉCART »*. C'était faux, et il a survécu à deux lots qui le citaient : **un
commentaire n'est pas un garde-fou** — c'est la troisième fois que ce dépôt
l'apprend (#562, #491, celui-ci).

### 4 ter. L'onglet ouvert par défaut est celui que le MENU annonce

Signalé le même jour : *« quand on clique sur prestataire, la page affichée par
défaut est celle des contrats »*. Une entrée de menu qui ouvre autre chose que ce
qu'elle nomme fait douter d'avoir cliqué au bon endroit.

**Règle** : l'onglet initial porte le nom de l'écran, sauf raison écrite sur
place. Une ouverture directe par son **adresse** reste prioritaire — c'est un choix
explicite du lien, pas un défaut.

## 5. Pill Buttons

**Quand** : choix exclusif ou multiple, ≤ 8 options, libellés courts.
**Préférer à** : `<select>`, `radio` en colonne, `checkbox` en colonne.

- Classes : `.perimetre-pills` (conteneur) — ⚠️ `.pill` et `.pill-active` ont été **retirées** le 29/08/2026 (#491) : `ecrans.css` le dit à deux endroits. Le rendu passe par `Pastille.svelte` (39 écrans), et `lint:seuil-listes` décide entre pastilles et liste déroulante selon le nombre d'entrées
- `type="button"` obligatoire (éviter soumission formulaire)
- Sélection multiple : toggle + reset auto vers défaut si aucun actif

Pages implémentées : `tickets` (filtre de nature, 23/09/2026) — le calendrier y est un filtre depuis #1092

### 🔢 Le compteur d'une rangée de filtres — le STANDARD (10/10/2026)

Arbitré à l'écran : un nombre dans CHAQUE pastille (maquette B, v2.130.0) puis
cinq variantes plus discrètes, et c'est la **J** qui a été retenue — *« compteur
uniquement pour la pastille retenue »*, à appliquer à toute nouvelle demande.

- **Quoi** : la pastille **retenue** — « Tous » compris — porte le nombre
  d'éléments que la liste **affiche**, filtres et recherche appliqués. Les autres
  pastilles n'en portent **aucun**. Deux rangées sur une même liste montrent
  donc le même nombre, chacune sur sa retenue.
- **Comment** : `compte={<liste affichée>.length}` sur `ChoixPastilles` (ou
  `FiltrePerimetre`) — UN nombre pour la rangée, jamais un par entrée. C'est
  `Pastille` qui décide qu'il ne se voit que sur la retenue (`Compte surAplat`).
  Un composant de filtres qui enveloppe la rangée reçoit le nombre de la page
  (`affichees`, `affiches`) : c'est la page qui tient la liste.
- **Lequel** : la liste **principale** — ce qui est rangé aux Archives a sa propre
  vignette en dessous, et ne compte pas (`enCours` de `#lib/archives`, sur le
  `archivee` que le serveur calcule).
- **Le style** : la vignette `Compte` des Archives, inversée sur l'aplat Bleu
  Seine — chiffres à chasse fixe, sans animation (`emil-design-eng` : ce qu'on
  voit à chaque clic ne s'anime pas).
- **Ce qui n'en porte pas** : un choix de FORMULAIRE (mode `radio`, ou entrée vide
  qui est une valeur — « Aucune », « Inchangé »), une bascule de VUE (Nouvelle /
  Archives, onglets de reporting), une liste déroulante (`PastilleDeroulante`).
- 🔒 `npm run lint:compte-filtres` refuse une rangée de filtres sans `compte` ;
  ses exceptions — des choix de formulaire — sont déclarées avec leur raison.
  `e2e/compte-filtres-affaires` éprouve le rendu.

## 5 bis. La RECHERCHE libre — Affaires (27/09/2026)

Le filtre « Catégorie » de la page Affaires a cédé la place à une recherche libre
(maquette A, avec l'extrait et les Archives de la C, arbitrée à l'écran) :
https://claude.ai/artifact/BRYAWNn4EZAx1EBTHHNMQu

- **La règle est au SERVEUR** (`app/utils/recherche_affaires.py`, `--selftest`) :
  tous les mots, partout, sans accents ni casse — n°, titre, description,
  catégorie, lieu, personnes, prestataire, équipement, suites, messages, pièces
  jointes. L'écran n'en a pas de seconde : `#lib/recherche-affaires` demande
  (après la frappe, dernière réponse seule) et filtre.
- 🔴 **Elle ne lit que ce que l'écran montre** : `ticket_visible` (l'affaire et son
  fil, depuis le 29/09/2026), `lit_les_notes_internes`, `document_visible` — les prédicats des routes qui
  montrent le même texte, jamais réécrits (`test_recherche_affaires.py`). Un
  compte de résultats est une information.
- La carte dit **où** : « Trouvé dans une suite », et le passage en segments
  surlignés (`ExtraitRecherche`) — du TEXTE, jamais du HTML : le `<mark>` est
  posé par le gabarit, il n'y a rien à assainir.
- Les **Archives** ne s'y mêlent que sur demande (case, ou « Les inclure » quand
  le bilan en signale).

## 6. Ligne de publication

🔴 **Cette section décrivait la ligne antérieure à `PastillesAffaire`** — « urgence :
bord gauche rouge uniquement (pas de badge texte) » — et contredisait le §3, qui
fait foi depuis le 27/09/2026 : le bord rouge **et** un seul glyphe, ⚡
(`GLYPHE_URGENCE`), « ⚡ Urgente » dans la dernière ligne de la carte, rendue par
`PastillesAffaire` (#1556).

- **L'ordre** des pastilles, la ligne d'auteur et l'urgence : §3 — une seule
  écriture, ne pas la recomposer ici.
- Badges : toujours **après** le titre.
- Épingle : badge absolu coin haut-gauche (`.pin-badge`).

## 7. Prévisualisation — 3 lignes dans une CARTE, 5 ailleurs

| Classe | Où | Depuis |
|---|---|---|
| `.clamp-3` | l'aperçu d'une **carte de liste** (`ApercuCarte`) | 18/09/2026 |
| `.clamp-3` | le **sous-texte** d'une pastille (`Pastille`, vignette de catégorie) | 25/09/2026 |
| `.clamp-5` | un bloc expansible qui **n'est pas** une carte | 15/08/2026 |
| `.clamp-2` | un **titre** de carte | 18/08/2026 |

Les trois vivent dans `styles/normes.css`, et nulle part ailleurs.
🔒 `npm run lint:clamp` refuse une troncature écrite ailleurs, et `.clamp-5`
dans un fichier qui rend une `.carte-liste`, et un sous-texte déclaré dans
`SOUS_TEXTES` qui ne porte pas `.clamp-3` (#1310).

⚠️ `.clamp-3` **existait déjà**, écrit à la main dans `FluxCard` : le fil
d'activité tronquait à trois lignes depuis toujours, et c'est lui qui a servi de
référence quand il a fallu choisir. L'écriture locale a été retirée le 18/09 —
une quatrième aurait suivi à la prochaine liste.

## 8. Archiver vs Supprimer

| Action | Qui | Où | API |
|--------|-----|-----|-----|
| 📦 Archiver | CS + admin | Vue principale | `PATCH { archivee: true }` |
| 🗑️ Supprimer | Admin seul | Vue Archives seule | `DELETE` (require_admin) |

Vue archives unifiée dans `tickets/+page.svelte` (onglet Archives) depuis que le calendrier y a été fondu (#1092).

🔴 Les affaires et actualités ne le respectaient pas jusqu'au 24/09/2026 : le 🗑️ de l'admin était dans la liste, et une actualité s'y effaçait entière. Pour une affaire, l'archivage est `archive_manuel` (`utils/archivage.REGLES`). 🔒 `api/tests/test_suppression_aux_archives.py`.

🔴 **Prestataires et contrats, jusqu'au 02/10/2026 (#1538)** : un 🗑️ intitulé « Archiver », sur la vue principale, pour tout le conseil — l'icône disait « supprimer », la boîte « archiver », la route `DELETE` — et l'objet rangé n'avait **plus d'écran**. Ils suivent désormais l'affaire :

| | Vue principale | Archives |
|---|---|---|
| Geste | 📦 Archiver (CS + admin), confirmé par `ARCHIVAGE` | ↩️ Restaurer, sans confirmation — ✏️ et ✨ se taisent : on ressort avant de corriger |
| Écran | la liste de l'onglet | section `TITRE_ARCHIVES` repliée sous elle, par `ListeEtArchives` — le même rendu, atténué (`.attenue`) |
| API | `PATCH …/archivage {archivee}` — UN mot pour ranger et ressortir (`archiverPuis`) | `GET …/archives`, à part : les autres lecteurs de la liste (formulaire d'affaire, reporting) ne voient pas surgir ce qu'on a rangé |

Aucune suppression définitive : il n'y a rien à garder derrière `archive`. La règle est déclarée dans `REGLES` (`champ_actif` : la colonne héritée `actif`, inversée) — aucun archivage par le temps. 🔒 Le même test refuse un 🗑️ hors d'un bloc `archive` dans **toute carte qui archive** (`_QUI_ARCHIVENT`), et un bouton « Archiver » qui ne montre pas 📦 ; `e2e/archives-prestataires` éprouve l'écran rendu.

## 9. Champs de formulaire

> 🔴 **La largeur de saisie appartient au SQUELETTE, pas à la page (R1) — et elle
> change (18/08/2026).** Elle est désormais une **variable**,
> `--largeur-saisie`, définie dans `styles/normes.css` et posée par
> `(app)/+layout.svelte` : *une largeur unique, quels que soient la page et le
> formulaire, adaptée à l'écran du terminal avec une marge optimale* (arbitrage
> utilisateur). Motif : le cap à 720 px était plus étroit que tout le reste de la
> page — la boîte de création s'arrêtait bien avant les cartes de la liste posées
> juste en dessous.
>
> **La nouvelle valeur (`100%` du conteneur) n'est active que sur `/tickets`**,
> le temps d'être constatée à l'écran (R5) ; partout ailleurs le défaut reste
> 720 px. ⚠️ **FAIT le 18/08/2026** : la valeur est généralisée, et la liste `ROUTES_LARGEUR_PLEINE` qui la limitait à une route **n'existe plus**. Ce paragraphe décrivait le travail à faire ; il décrit maintenant ce qui est. Généraliser aurait été = changer la ligne de `styles/normes.css` et supprimer la liste
> `ROUTES_LARGEUR_PLEINE` du squelette. Ne pas la laisser vivre : un mécanisme
> d'exception qui survit invite la valeur suivante — c'est la leçon de la prop
> `marge` d'`EntetePage` (§13). Ne **jamais** écrire une largeur dans une page.

**Largeur : `.largeur-saisie`, sur le conteneur du formulaire.** Vaut
pour les pages dédiées *et* les formulaires intégrés à une liste — le même geste
ne doit pas avoir deux largeurs selon l'écran.

Trois pratiques coexistaient avant le 15/08/2026 : 640 px sur les pages dédiées et
l'administration, pleine largeur sur les formulaires inline (actualités,
sondages). Signalé par l'utilisateur, pas par un contrôle.

⚠️ Les séparateurs `<hr>` d'un bloc de saisie portent la **même** classe : sinon
le trait s'arrête avant le formulaire, ce qui se voit immédiatement.

⚠️ Ne s'applique **pas aux modales**, qui ont leurs propres contraintes (celle du
calendrier reste à 640 px, délibérément).


- Champ requis : `<EtoileRequis vide={!champ} />`, jamais une astérisque tapée

  🔴 Elle est **collée** au libellé — `TITRE*` — et **ROUGE tant que le champ
  est vide**, la couleur du libellé sinon (livré le 22/09/2026, #1121). Elle
  cesse d'être une décoration : c'est l'**état** du champ, lisible d'un coup
  d'œil sur un formulaire où toutes les sections s'alignent.

  🔴 **Une valeur par défaut ACTIVE est une valeur** (27/09/2026, signalé à
  l'écran : « * rouge, c'est uniquement s'il n'y a aucune valeur »). Destinataires
  et Périmètre rangent leur défaut en liste VIDE — « Tous », « aucune
  restriction » — que le sélecteur affiche comme choisi ; leur `rempli` le
  compte (`concerneTousLesResidents`, `estPerimetreParDefaut`). Une section qui
  stocke son défaut autrement que par sa valeur doit faire de même.
  🔒 `e2e/etoile-valeur-defaut.spec.ts` (affaire et actualité, et le Titre vide
  reste rouge — la preuve que le test voit le rouge).

  Un caractère ne sait pas si le champ est vide : c'est pour cela qu'il y a un
  composant. Il était écrit **trente-cinq fois** — vingt-six `<label>Titre *`
  en clair et cinq composants qui calculaient `{requis ? ' *' : ''}` —, et
  aucun de ces points ne connaissait la valeur. 🔒 `npm run lint:champs`.

  ⚠️ **Dans un `label.field` qui ENVELOPPE son champ**, le texte et l'étoile
  vont dans un `<span>` : ce libellé est une colonne flex, et posés à nu ils y
  deviennent deux lignes — l'étoile tombait sous « Début » (#1230, mesuré par
  `e2e/etoile-requis.spec.ts`, refusé par `lint:champs`).

  ⚠️ Les libellés de champ sont en **MAJUSCULES par le style**
  (`.field label`, `champs.css`), comme les intitulés de section. Jamais
  tapées : `TITRE` écrit en dur est épelé lettre à lettre par certains
  lecteurs d'écran, et une règle qui change obligerait à rouvrir chaque écran.
  🔒 **Le libellé seul** : quand il enveloppe son champ (`label.field`), sa phrase
  d'aide, ses cases à cocher, un bouton gardent leur casse — la liste vit dans
  `champs.css`, et `lint:champs` refuse un enfant qu'elle oublierait (#1315 :
  « tout l'admin est en majuscules »).
- **Pas** de mention « (optionnel) » : l'absence de `*` suffit
- Actions : bouton secondaire / Annuler **à gauche**, action primaire **à droite**

### Un champ, UNE nomenclature : `.field`

🔴 **`.field` (`styles/champs.css`) est la définition unique du champ** — mise en page,
fond beige, contour de focus, état lecture seule. Les deux écritures conviennent,
et elles seules :

```svelte
<label class="field">Titre *<input type="text" bind:value={titre} /></label>

<div class="field">
  <label for="ah-source">Pré-remplir depuis une actualité</label>
  <select id="ah-source" bind:value={source}>…</select>
</div>
```

**Le champ ne porte aucune classe** : `.field input`, `.field select` et
`.field textarea` le gouvernent. Deux modificateurs nommés, et rien d’autre :
`champ-large` (§9 bis) et **`champ-en-ligne`**, pour un champ posé dans une
rangée où le `gap` du parent porte déjà l’espacement.

🔒 **Garde-fou : `npm run lint:champs`** (`front/scripts/check-champs.mjs`), en CI
depuis le 19/08/2026. Tout `<input>` de saisie, `<select>` ou `<textarea>`
**associé à un libellé** doit vivre dans un `.field`. Un contrôle **sans**
libellé — filtre de barre d’outils, recherche, renommage en ligne — est hors
périmètre : l’y forcer donnerait des dérogations à la pelle, donc un contrôle
qu’on désarme.

**Why (#413, 19/08/2026)** : **six** nomenclatures coexistaient — `.field-label`
(3 définitions **incompatibles** : deux enveloppantes, une frère), `.form-group`
(3), `.champ`, `.ah-champ`/`.ah-select`, `.email-label`/`.email-input`, et le
`<label>` nu appuyé sur une règle `.form-grid label`. **Trois fichiers
redéfinissaient `.field` elle-même**, le nom canonique, avec d’autres valeurs.

⚠️ Et **deux ne renvoyaient à aucune définition** : `OngletWhatsApp` et
`acces-securite`, extraits d’`admin` sans ses styles, rendaient leurs champs nus
en production — `.form-grid` comprise, si bien que leurs formulaires n’étaient
même pas des grilles. C’est la régression des pastilles nues (v2.67.11),
appliquée au formulaire.

⚠️ **La leçon du contrôle, et c’est la vraie.** Le relevé de #374 cherchait un
`<label>` qui enveloppe son champ *sur une ligne*. Il a manqué la forme
multi-lignes (deux champs d’Admin), puis la forme « libellé frère » reliée par
`for=` — celle-là trouvée **en production par l’utilisateur**, un fond blanc au
milieu d’un site beige. Un relevé par motif textuel ne prouve rien sur ce qu’il
n’a pas cherché : `lint:champs` lit l’**arbre des balises**, où les trois formes
se ramènent à une seule question, et son `--selftest` le montre les refuser.

### Fusionner deux écrans : une UNION, jamais un remplacement

Deux écrans qui montrent la même donnée sous deux angles se fusionnent — mais la
fusion se **prouve capacité par capacité**, sinon elle en retire en silence. Les
« Modèles e-mail » et les « Designs des modèles d’e-mail » l’ont été le
19/08/2026, après avoir coexisté depuis #299 et attendu leur arbitrage dans #307.

Le geste, dans cet ordre :

1. **Dresser le tableau des capacités** de chacun, à la lecture du code — pas de
   mémoire. Ici : quatre venaient de l’écran secondaire (intention, aperçu du
   rendu, variables du gabarit, réinitialisation des designs), trois du principal
   (table, corps texte, historique des envois).
2. **Vérifier que les deux parlent au même endpoint.** C’était le cas
   (`/admin/modeles-email`), et le serveur acceptait déjà les cinq champs : la
   fusion ne demandait aucun changement d’API.
3. **Distinguer une capacité d’une promesse vide.** Le regroupement « par
   domaine » n’a pas été repris : `ModeleEmail` n’a ni `domaine` ni `categorie`,
   l’écran rangeait donc tout dans un unique groupe « général ».
4. ⚠️ **Reprendre, c’est relire.** « Variables disponibles » découpait sur les
   virgules un champ qui est un **tableau JSON**, et affichait `{{ ["civilite" }}`.
   Recopier le geste aurait recopié le défaut ; il est corrigé en le reprenant,
   avec un repli sur l’ancien format et cinq cas éprouvés.

🔴 **Le compte final se vérifie**, capacité par capacité, avant de supprimer
l’écran absorbé. C’est le seul moment où la perte est encore réversible.

### L’administration est UNE page — plus aucun écran autonome

Arbitré à l’écran le 19/08/2026 : *« fiche copropriété et Périmètre sont des pages
autonomes alors que les autres sont intégrées au menu Paramétrage : uniformise cela,
cela évitera le retour que je t’ai demandé »*.

🔴 **Un écran d’administration est un ONGLET de `admin/+page.svelte`, jamais une
route.** Les sept qui vivaient sur `/admin/<écran>` — fiche copropriété, périmètres,
audit lots, les trois imports, designs d’e-mail — sont devenus des composants
`Onglet*.svelte`. On ne quitte plus Paramétrage : le bouton « ← Retour » posé la
veille n’avait plus d’objet, et il a disparu.

| Ce qui fait foi | Où |
|---|---|
| la liste des onglets | la **table des pages**, bloc `admin` de `pages-roles.ts` — libellé, descriptif, `groupe`, route `/admin?onglet=<id>` ; la page la lit (`PAGES`) et n’en tient plus de seconde (01/10/2026) |
| les rangées | `BarreOnglets pageId="admin"` — **deux rangées** dès que la table porte plusieurs `groupe` : les groupes (des liens vers leur premier onglet ouvert, le compte rouge additionné), puis les onglets du groupe actif ; le descriptif de l’onglet actif dessous ; libellés et descriptifs se modifient dans **Menu et pages** |
| l’ouverture directe | `/admin?onglet=perimetres` — lue dans l’adresse (`$page.url`), chaque onglet est un lien |
| le panneau | un composant `Onglet*.svelte`, jamais du balisage dans la page |

⚠️ **La table et les rendus doivent concorder** : un onglet déclaré sans bloc
`{:else if onglet === …}` affiche une page vide, un bloc sans déclaration n’a pas de
bouton. Les deux sont silencieux — `npm run lint:routes` les refuse, et exige que la
page rende `BarreOnglets` et lise la table. Il refusait jusqu’au 01/10/2026 une
TROISIÈME liste, les boutons écrits à la main : `BarreOnglets` la tient désormais par
construction.

🔴 **Ce qui attend un geste de l’admin est UN onglet, « À traiter »** (01/10/2026) —
comptes en attente, commandes d’accès, demandes de profil, en `SectionRepliee`
`enSerie` et en accordéon (`surBascule` + `basculer`) : la pastille de l’onglet
additionne les trois, la première section non vide s’ouvre seule. Une quatrième
file s’y ajoute comme section, jamais comme onglet. Pas de redirection des
anciennes clés (`comptes`, `acces`, `demandes_profil`) : arbitré, les liens
émis par l’API ont été corrigés à la place. La Télémétrie est rangée sous
« Personnes ».

🔴 **Rangée par niveau en six groupes** (#2062, maquette validée le 21/10/2026,
variante A) — 👥 Personnes · 📥 Imports · 🏢 Copropriété · 🔌 Services ·
🎨 Présentation · 🛠 Exploitation : un groupe par question, l’ordre et le contenu
se lisent dans la table. **Un groupe ne se réserve pas, ses onglets si** :
l’Exploitation reste visible de l’administrateur (Maintenance, `ouvertOperateur`)
et de l’opérateur (Installation, Installations : `reserve: 'operateur'`). Un onglet
refusé se replie sur le premier ouvert de **son groupe**. Contrairement à « À
traiter », les clés retirées ce jour-là (`site`, `import_*`) **sont redirigées** :
un modèle de courriel en base porte `import_tc`, et la base n’est pas le seed —
`#lib/admin-adresses`, une clé ne s’en retire jamais. 🔒 `e2e/admin-groupes.spec.ts`
parcourt les dix-neuf clés d’avant, et les trois comptes.

⚠️ **Un lien vers un écran d’admin s’écrit `/admin?onglet=<clé>`.** Un modèle
d’e-mail pointait encore vers `/admin/telecommandes-import` : `test_liens_front.py`
l’a attrapé — sans lui, le destinataire du message « Vérifier les imports » serait
tombé sur une 404.

### L’anatomie d’un écran d’administration

Arbitré à l’écran le 19/08/2026 : *« l’écran WhatsApp n’est pas très beau, fais
ressortir les sections, on s’y perd visuellement »*, puis *« uniformise les
en-têtes avec la possibilité d’un retour »*, *« uniformise le footer »*, *« le look
des formulaires ne correspond pas à l’UX »*.

Chaque fois, le motif **existait déjà** et n’était pas employé. C’est la forme la
plus coûteuse du défaut : on croit avoir une charte, on a des copies.

| Élément | Le motif | Il était écrit à la main… |
|---|---|---|
| en-tête de page | `EntetePage` + `retour="/admin"` | 4 écrans sur 8, dont un **sans aucun retour** |
| bloc | `<section class="card config-section">` | `.config-section` n’avait **aucun fond** |
| sous-section | `SectionFormulaire` (+ `icone`) | un `<p>` gris gras, **16 fois**, et un `<hr>` **8 fois** |
| barre d’actions | `.form-actions` | **13 fois** en style en ligne, avec **4 marges différentes** |
| pied de modale | `.modal-footer` | 4 en ligne, 2 sous `.modal-actions` — **définie nulle part** |

🔴 **Le fond du champ est le BEIGE, celui de la carte est le BLANC.** Une couleur,
un rôle : le champ se lit comme un creux dans la carte. Cela n’a de sens que si
la carte est franchement blanche — les blocs d’admin étaient posés à même le fond
de page, qui est **le même beige que les champs**, si bien qu’un champ n’avait plus
que sa bordure pour exister. ⚠️ Ce beige n’avait jamais été décidé : `styles/composants.css`
portait `.field input` **deux fois**, une version blanche et une beige, et c’est
l’ordre de la cascade qui tranchait (#413).

⚠️ **Pas d’émoji dans un titre de section ni de bloc** : le tracé vient du
catalogue partagé `#lib/icones-svg.json`, via `icone` sur `SectionFormulaire` ou
`<Icon>` sur `.config-section-title`. Un émoji dépend de la police du système ;
l’en-tête de page prenait déjà ses tracés dans le catalogue — deux façons de
désigner une section, dont une seule est stable.

⚠️ **`.form-actions` n’est pas `.modal-footer`.** La première soumet un
formulaire, la seconde ferme une boîte de dialogue — et `lint:soumission` ne
regarde que la première, à raison : « Confirmer » est le bon verbe pour une
confirmation, « Enregistrer » pour une soumission.

### 9 bis bis. LA phrase grise qui explique : `.aide`, et rien d'autre

Un seul nom pour la notion, un seul endroit (`champs.css`), un seul modificateur :

```svelte
<p class="aide">0 = rez-de-chaussée, 2 = 2ème étage.</p>
<p class="aide sous-case">Le message part à la prochaine sauvegarde.</p>
```

`sous-case` est le **seul** écart, et il porte sa raison : l'aide d'une case à
cocher s'aligne sous son libellé, et cette indentation EST son contenu.

🔴 **Il y en avait NEUF le 10/09/2026** — `.field-hint` (49 occurrences), `.aide`
(10), `.aide-bloc` (8), `.aide-case` (5), plus quatre classes **locales** que
l'audit de la charte ne pouvait pas voir : `.aide-champ` (copie littérale de
`.field-hint`), `.aide-reponses`, `.aide-tache`, `.aide-source`. Le ticket #870
n'en avait relevé que quatre.

⚠️ **La géométrie retenue est celle de la plus déployée**, pas la moyenne des
neuf : `margin: .25rem 0 0`, 0.78rem, interligne 1.45. L'ancienne `.aide` portait
une marge **négative** en haut — et **deux écrans sur quatre l'écrasaient
localement**. Ce n'étaient pas eux les cas particuliers : c'était la valeur qui
était fausse. *Une marge négative dans une classe de texte compense l'espacement
de quelqu'un d'autre — c'est un symptôme, jamais une intention.*

⚠️ Ne pas confondre avec `.grille-champs` (inscription), qui s'appelait
`.aide-grille` : ce n'est pas une aide, c'est un conteneur de grille. Renommée le
même jour pour qu'un futur audit ne la compte pas dixième.

### 9 bis. Ce qui décide de la largeur d'un champ, c'est son CONTENU

Les grilles (`.form-grid`) répartissent en colonnes de ~180-200 px. C'est juste
pour un champ **court** — date, montant, statut, fréquence — et faux pour tout le
reste : un titre y est écrasé dans le tiers le plus étroit, et un sélecteur de
périmètre y empile ses dix pastilles **une par ligne**, description comprimée.

**Ces champs prennent la LIGNE ENTIÈRE — `class="champ-large"` (`styles/champs.css`) :**

| Champ | Pourquoi |
|---|---|
| **Titre**, **Libellé** | texte libre, souvent long |
| **Description**, **Contenu**, **Notes** | éditeur riche, plusieurs lignes |
| **Périmètre** | pastilles + second niveau + description du nœud |
| **Destinataires** | pastilles de profils |

La classe se pose **sur le champ**, jamais sur la grille : c'est le contenu qui
décide de sa largeur, pas l'écran qui l'accueille.

**Why (16/08/2026)** : signalé **trois fois de suite** par l'utilisateur, sur trois
écrans différents — prestation, contrat, puis calendrier. Même défaut à chaque fois,
et chaque fois trouvé à l'œil après livraison.

### 9 ter. L'ordre est toujours : **Périmètre, puis Destinataires**

Le périmètre dit *de quoi* il s'agit, les destinataires *à qui* on l'adresse — le
premier cadre le second. Un écran qui les inverse fait relire deux fois.

### 9 quater. Le badge d'état à côté du libellé

Quand un sélecteur multiple a un défaut ou une sélection résumable, il porte un
**badge** à droite de son libellé : `Profils destinataires [Tous]`,
`Périmètre [Toute la résidence]`. On lit l'état sans dépiler les pastilles.
Inauguré par le sondage ; l'utilisateur a demandé de l'étendre au **standard** —
donc à `PerimetrePicker` et au sélecteur de destinataires, partout.

### 9 sexies. L'ORDRE des champs est imposé — il ne se discute pas par écran

| # | Section | Qui l'écrit |
|---|---|---|
| 1 | **Titre** | l'écran |
| 2 | **Champs spécifiques** à la page | l'écran |
| 3 | **Options de publication** — si l'objet en a | `ChampsCommuns` |
| 4 | **Workflow** — si l'objet en a un | `ChampsCommuns` (contenu par `slot`) |
| 5 | **Périmètre** | `ChampsCommuns` |
| 6 | **Destinataires** | `ChampsCommuns` |
| 7 | **Description** | `ChampsCommuns` |
| 8 | **Photos** | `ChampsCommuns` |
| 9 | **Documents** | `ChampsCommuns` |
| 10 | **Diffusion** | `ChampsCommuns` |

> ⚠️ **Périmé** : cette table date d'avant le 21/09/2026 (#1095 a scindé, ajouté et
> déplacé des sections). L'ordre se lit dans `SECTIONS_ORDRE`, et nulle part ici —
> arbitrage n° 53.

🔴 **Révisé le 12/09/2026, et surtout CONTRÔLÉ depuis.** « Options de
publication » n'avait aucun rang : chaque écran la posait où il voulait, et
l'utilisateur a vu la divergence — entre Actualité et Tickets d'une part, et
dans le calendrier d'autre part, où « Épingler dans le fil » vivait carrément
dans la **Diffusion**, avec son propre glyphe, alors que
`#lib/options-publication` porte la notion.

⚠️ **Les deux écarts avaient la même cause** : cette table existait et rien ne
la faisait respecter. Elle est désormais tenue par deux mécanismes, pas par la
bonne volonté :

* `ChampsCommuns` rend les sections **3 à 10** — l'écran ne décide plus de leur
  rang, seulement de leur PRÉSENCE (`avecOptions`, `avecWorkflow`…) ;
* 🔒 `npm run lint:ordre-sections` refuse une section de rang inférieur écrite
  après une supérieure, dans **tout** `.svelte` du dépôt. Vérifié échouant sur
  le défaut, et son lecteur de balise l'est aussi : un `=>` dans les props
  coupait la lecture, et le contrôle passait au vert sur ce qu'il devait refuser.
  Depuis le 27/09/2026 (#1329), il classe aussi les intitulés **propres à un
  objet** (« Code », « Type », « État ») : ils se lisent dans le `titreEcran`
  de l'entité que le fichier importe. Un formulaire qui n'importe pas sa
  déclaration reste donc à moitié invisible — **déclarer l'entité, c'est ce qui
  la fait contrôler**.
* 🔒 `npm run lint:pliage-transmis` (22/09/2026) tient l'autre bout du même
  fil : un composant qui **porte** une section du cadre — `SectionsPiecesJointes`,
  `ChampSaisiPour`, `SectionWorkflow` — doit **transmettre** son pliage. Sans
  prop `pliable`, la table a beau dire `pliee: true`, la section s'ouvre.
  Signalé deux fois à l'écran avant qu'un contrôle le voie : corriger la table
  ne suffit pas si le porteur ne la lit pas.

⚠️ Un épinglage ne se met JAMAIS dans la Diffusion, même quand il en dépend. Le
calendrier avait un motif réel — un événement absent du fil ne peut pas y être
épinglé — mais **une dépendance n'est pas un rang** : elle se dit
(`epingleInterdit`, qui désactive la case *et écrit pourquoi*), elle ne déplace
pas la section.

**Workflow et Diffusion sont deux notions distinctes**, et les confondre est
l'erreur qui a fait poser la question :

| | Workflow | Diffusion |
|---|---|---|
| Répond à | *où en est cet objet ?* | *qui le voit, et où ?* |
| Contient | Ouvert / En cours / Résolu (ticket), Suivi Kanban (événement, prestation) | affichage au fil, épinglage, WhatsApp, syndic, conseil syndical, Publié / Brouillon |
| Se place | **avant** le Périmètre — c'est un champ spécifique de l'objet | **en fin**, après les documents |

🔴 **Le KANBAN du calendrier EST un workflow** (18/08/2026). Ses six colonnes —
AG · CS · Syndic · Prestataire · Terminé · Annulé — répondent exactement à *« où
en est cet objet ? »*. La section s'appelle donc **Workflow**, et non « Suivi
Kanban » : ce dernier nommait l'écran où on le voit, pas la notion. **Aucun
second champ d'état n'a été créé** — deux notions de suivi sur le même objet se
contredisent au premier écart, et rien ne dirait laquelle fait foi.

Corollaire : **un changement de colonne est une transition tracée**, avec son
avant et son après dans l'Historique ; toute autre modification reste une
correction. Le calendrier était le dernier écran du site à faire avancer un suivi
en silence.

🔴 **Ce qu'une entrée d'Historique ENVOIE parle d'ELLE** (18/08/2026). Rouvrir
la Diffusion sur un suivi ne suffit pas : il faut recâbler ce qui part. Le lot
de la veille avait ouvert la section et laissé l'appel existant — le groupe
WhatsApp recevait donc la description de l'ÉVÉNEMENT à chaque commentaire, le
même texte indéfiniment, et l'e-mail attachait les pièces de l'événement au
lieu de celles de l'entrée.

⚠️ **C'est le défaut typique de l'ajout d'un canal à une entité existante** :
on reprend l'appel qui marche, et l'appel qui marche parle de l'objet porteur.
Rien ne lève, rien ne manque dans les journaux — le message part, il est
simplement faux. Trois questions à se poser, dans cet ordre :

1. **le contenu** — texte de l'entrée, pas de l'objet ;
2. **les pièces** — celles de l'entrée, avec repli sur l'objet si elle n'en a
   pas (même règle que `flux/tickets.py`) ;
3. **le renvoi** — un commentaire se lit hors contexte : le message porte un
   lien vers l'objet, sinon le lecteur ne sait pas sur quoi il porte.

🔴 **Et le FIL doit apprendre la nouvelle table.** Le fil est une douzaine de
rubriques indépendantes ; rien n'oblige une table neuve à s'y déclarer.
Le fil des événements (`flux/evenements.py`, supprimé avec #1092) ne lisait que `Evenement` et datait donc ses cartes de
l'annonce — une affaire qui avançait aujourd'hui restait noyée dans les
vieilles lignes. **Le fil date du dernier fait, jamais du premier.**

⚠️ Ajouter un TYPE pour la mise à jour aurait été le réflexe (c'est ce que font
les tickets, avec trois types). **Ne pas le faire ici** : le front teste
`type === 'evenement'` à six endroits — libellé, couleur, fond, lien, urgence,
et le filtre du tableau de bord qui **masque les AG** à qui n'y a pas droit. Un
type neuf serait passé à côté des six, et une AG commentée serait devenue
visible de tous, en silence. **C'est la donnée qui porte la différence** :
`evol_contenu` présent ⇒ la carte rend le bloc de suivi.

### 9 septies. Les sections communes ne se réécrivent plus : `ChampsCommuns.svelte`

**L'ordre ci-dessus a un point d'héritage depuis le 16/08/2026.** Périmètre,
Destinataires, Description, Pièces jointes et Diffusion sont rendus par UN
composant, qui porte leur ordre, leurs intitulés et leurs séparations
(`SectionFormulaire`). Un écran déclare ce qu'il a, jamais où le mettre :

```svelte
<ChampsCommuns
  idPrefixe="ticket"
  avecPerimetre bind:perimetre={perimetreCible}
  avecDescription descriptionRequise bind:description
  avecPhotos bind:photos={photosUrls}
  avecDocuments bind:documents={fichiersUrls}
  avecDiffusion bind:whatsapp bind:syndic bind:cs
>
  <svelte:fragment slot="diffusion">…options propres à l'écran…</svelte:fragment>
</ChampsCommuns>
```

Les sections **1 à 3** (Titre, champs spécifiques, Workflow) restent dans l'écran :
lui seul sait ce qu'elles portent.

🔴 **Une Description se rend par `SectionDescription`**, assistant IA et marque ✨
compris — jamais un `RichEditor` posé sous un intitulé « Description ». L'annonce
de hall le faisait, sous « Message » : seule Description du site privée de
l'assistant (#1089). 🔒 `npm run lint:description-unique` ; deux écarts LÉGITIMES y
sont déclarés — le descriptif d'une page du menu, et le contrat, qui garde sa
synthèse IA seule (arbitré, #1240).

#### Une section à UN seul champ ne répète pas son nom

Première livraison, l'écran affichait :

```
PÉRIMÈTRE
Périmètre *                            [Copropriété entière]
```

Le nom deux fois, en deux typographies — signalé par l'utilisateur, capture à
l'appui, **le jour même de la mise en production**. La cause est mécanique :
`PerimetrePicker`, `DestinatairePicker` et `FichiersUpload` portent chacun leur
intitulé (c'est justement leur point d'héritage, §9 quater), et la section en
ajoutait un second.

**Règle** : quand une section ne contient qu'un champ, le **titre de section EST
le libellé**. Il porte l'astérisque (`requis`) et le badge d'état (`badge`) ; le
champ reçoit `titre=""` et n'écrit plus rien.

```
PÉRIMÈTRE *                            [Copropriété entière]
```

Les sections à **plusieurs** champs (Détails, Clôture, Diffusion) gardent leur
titre de groupe **et** les libellés de leurs champs : ce n'est pas une redite,
c'est une hiérarchie.

🔴 **La section 1 aussi** (23/09/2026, signalé à l'écran : *« normalise les
titres des sections »*). Sept formulaires l'ouvraient par un `<label>` de champ
sous une `SectionFormulaire` sans titre : TITRE prenait le style d'un libellé
(0,875 rem, graisse 500), CATÉGORIE juste dessous celui d'une section (0,72 rem,
gras). Elle vit dans **`SectionTitre`** (« Titre », ou « Nom », « Question »),
et `npm run lint:section-nommee` refuse une section nommée par son champ.

**Hiérarchie** (arbitrée le même jour) : dans une section à plusieurs champs, le
libellé d'un champ se lit **un cran sous** le titre de section — même corps et
mêmes capitales, graisse moyenne, couleur atténuée (`champs.css`,
`.section-formulaire .field > label`). Il était plus GRAND que son titre de
section, et la hiérarchie se lisait à l'envers. Hors section (connexion,
réglages), le libellé est le seul repère et garde sa taille.

⚠️ **Le titre de section est un vrai libellé, donc il s'associe.** `SectionFormulaire`
rend un `<label for>` quand la section porte un contrôle **labelable** (`<select>`,
`<input>`) — prop `pour` —, et un `<h4 id>` sinon, l'appelant reliant son groupe par
`aria-labelledby` (prop `idTitre`). Les pastilles et l'éditeur riche ne sont PAS
labelables : un `for` posé dessus n'associe rien, **et le fait en silence**. C'est
d'ailleurs ce qui existait avant — `Périmètre *` était un `<div>`, donc un groupe de
boutons sans nom pour un lecteur d'écran.

Corollaire appliqué au passage : le `(max N)` a quitté l'intitulé des pièces
jointes. Le compteur `0/N` sous le bouton le dit déjà, et il le dit mieux — il se
met à jour. Les types acceptés sont en aide grise à côté du compteur, déduits
d'`ACCEPT_DOCUMENTS` et non récités.

**Why.** L'ordre était écrit, `SectionFormulaire` savait séparer — et les six
formulaires recomposaient quand même la suite à la main. L'utilisateur l'a
signalé ainsi : *« Les objets ont l'air d'être dupliqués, pas instanciés, car ils
diffèrent selon les pages. »* Relevé avant correction :

| Notion | Ce qui divergeait |
|---|---|
| Description | « Description » / « Description * » / « Notes » ; hauteur 60, 80, 90, 100 ou 120 px |
| Documents | `FichiersUpload` sur tickets et calendrier, `<input type="file">` **nu** sur actualités et prestations |
| Diffusion | aucune section nommée sur **4 écrans sur 6** |
| Ordre | Périmètre au milieu de la grille des champs spécifiques (prestations) ; Kanban rangé dans la diffusion (calendrier) ; « Saisi pour » **après** les pièces jointes (tickets) |

Aucune n'était voulue : ce sont les six recopies qui les produisent. La seule
façon de ne pas les voir revenir est qu'un seul endroit les écrive.

⚠️ **Une rubrique dont le parent n'existe pas encore** (documents d'actualité,
fichiers de prestation : leur endpoint réclame l'identifiant) passe par le mode
**différé** de `FichiersUpload` — `documentsDifferes` + `bind:documentsFichiers`.
L'écran téléverse après création. Ne PAS retomber sur un `<input type="file">`
nu : c'est ce qui produisait la deuxième apparence.

### 9 octies. Jamais de sélecteur d'ÉLÉMENT nu dans un composant

`input`, `textarea`, `select`, `button`, `label` seuls, dans un `<style>` de page
ou de composant : **interdit**, et refusé par `npm run lint:styles`.

**Why.** `sondages/+page.svelte` portait `input, textarea { width: 100% }`. Le
sélecteur visait les champs de saisie et atteignait **toutes les cases à cocher
de la page** : chacune s'étirait sur la largeur du formulaire et repoussait son
libellé à l'autre bout. L'utilisateur l'a signalé sur **deux écrans distincts**
(« Nouveau sondage » et « Déposer une annonce »), sans lien apparent entre eux —
c'était une seule ligne. Quatre composants annulaient déjà ce genre de règle case
par case avec un `style="width:auto"` recopié : le signe qu'on soignait le
symptôme.

Qualifier le sélecteur (`.case input[type="checkbox"]`) ou porter la règle dans
`styles/composants.css`, où elle est globale et assumée.

### 9 quinquies bis. Le bouton de soumission dit **« Enregistrer »**, partout

Verbe **générique**, sur tous les formulaires de création. Arbitré par
l'utilisateur le 17/08/2026 (#396), après un relevé de sept formulaires portant
**six** libellés — « Publier » / « Enregistrer brouillon », « Envoyer la demande »,
« Créer le sondage », « Publier l'annonce », « Soumettre », « Enregistrer » — plus
« Soumettre la demande » sur accès & badges, que le relevé du ticket avait manqué.

Aucun n'était faux ; l'ensemble n'avait pas de logique.

| | |
|---|---|
| au repos | `Enregistrer` |
| pendant l'envoi | `Enregistrement…` |

L'état d'attente est **inclus dans la règle** : il divergeait pareillement
(« Envoi… », « Création… », « Sauvegarde… », et même « … » tout court). C'est le
même libellé, vu pendant la seconde où l'utilisateur se demande si son geste a été
pris.

⚠️ **Le mode brouillon ne se dit plus dans le bouton.** L'actualité affichait
« Enregistrer brouillon » ou « Publier » selon la case cochée — or cette case est
déjà visible dans la section Diffusion, juste au-dessus. Le bouton la répétait.

**Hors périmètre, et volontairement** : les écrans d'authentification
(« Se connecter », « Créer mon compte »), les imports (« Importer ») et le
changement de mot de passe. Ce ne sont pas des créations d'objet.

**Garde-fou** : `npm run lint:soumission` (job `build-frontend`), sur les
composants `Formulaire*.svelte`. Les exceptions sont nommées avec leur raison et
le contrôle échoue si l'une devient inutile.

### 9 quinquies. Le bouton de soumission est **à droite**, via `.form-actions`

`.form-actions` (`styles/composants.css`) porte `justify-content: flex-end`. Un bouton posé nu dans
un `<form>` se cale à **gauche** et détonne : c'était le cas des sondages (« Créer
le sondage », « Publier l'annonce », « Soumettre » d'une idée), seuls de tout le
site, jusqu'au 16/08/2026. Ne jamais écrire un bouton de soumission hors de
`.form-actions`.

> ⚠️ **Question de nommage ouverte** (posée le 16/08/2026, non tranchée) : unifier
> **Libellé → Titre** et **Notes / Contenu → Description** ? C'est une décision
> fonctionnelle qui touche les libellés vus par les résidents, pas un renommage
> de classe.

## 10. Fil d'évolutions

Structure pour les tickets/publications avec historique :

- `.evol-list` : border autour, séparateurs `<hr class="evol-sep">`
- `.evol-item` : `.evol-icon` + `.evol-body` (`.evol-meta` + `.evol-text`)
- Pagination : si > 7 → afficher 5 + bouton `.evol-more`
- Formulaire inline : pills type + textarea + select statut → `.evol-form`

### 10 bis. Le workflow d'un objet : UNE liste, et UN geste par écran

**Les états proposables ne s'écrivent jamais dans un écran.** Pour un ticket, ils
viennent de `#lib/tickets` (`STATUT_TICKET_OPTIONS`, `…_LABELS`, `…_BADGE`,
`STATUTS_TICKET_FILTRE`, `estTicketActif`, `estTicketClos`), qui répond à
`StatutTicket` côté serveur. `api/tests/test_statuts_tickets.py` échoue sur toute
liste réécrite — y compris dans un fichier qui importe déjà le module.

**Où se change l'état :**

| Écran | Geste |
|---|---|
| `/tickets`, `/espace-cs` (listes), `/tickets/[id]` (lien direct) | formulaire d'évolution — état **et** commentaire en un envoi |

La fiche portait **les deux**, à quelques centimètres l'une de l'autre, et elles
ne proposaient pas les mêmes états (#415). Ses boutons « Changer le statut » sont
partis le 15/10/2026 avec elle : le lien direct rend la carte (§13).
 Un geste, un endroit : quand deux
commandes font la même chose sur un écran, ce n'est pas une commodité, c'est une
question posée à l'utilisateur — et deux occasions de diverger.

⚠️ `EvolForm` masque sa rangée de pastilles quand `statutOptions` est vide : un
choix à un seul choix n'est pas un choix.

**Ce qui a rendu la divergence invisible** : les cinq listes relevées étaient
chacune cohérente avec elle-même. Deux listes d'accord entre elles ne prouvent
rien — le seul contrôle qui vaille compare ce que l'écran **propose** à ce que
l'endpoint **accepte**.

## 11. Vignette & galerie de photos

Composants partagés. **Ne pas recréer** de `.xxx-thumb`, de rangée de photos ad hoc,
ni de visionneuse : `PiecesJointes` était déjà réécrit à l'identique dans quatre pages,
chacune avec sa propre expression régulière pour décider ce qui est une image.

| Composant | Rôle | Props |
|---|---|---|
| `#lib/components/PiecesJointes.svelte` | **affichage en lecture seule** d'une liste de pièces jointes (photos + documents) | `urls`, `size`, `compact`, `format` |
| `#lib/components/Lightbox.svelte` | visionneuse plein écran | `photos`, `index` · événement `fermer` |
| `#lib/components/Vignette.svelte` | vignette carrée (brique de bas niveau) | `src`, `alt`, `placeholder`, `count`, `size`, slot d'actions |
| `#lib/components/FichiersUpload.svelte` | galerie **éditable** — photos **et** documents ; `ImageUpload.svelte` pour une image seule. ⚠️ Cette ligne nommait `PhotosUpload.svelte`, qui n'existe pas | `urls`, `max`, `readonly`, `upload`, `remove` |
| `#lib/components/FichiersUpload.svelte` | **saisie** de pièces jointes ; `differe` retient les `File` quand le parent n'existe pas encore | `urls`, `fichiers`, `differe`, `mode`, `max`, `titre` |

Le téléversement est **délégué par callback** : chaque rubrique garde son propre
endpoint, le composant ne connaît pas l'API. La règle « qu'est-ce qu'une image, et
quel nom afficher » vit dans `#lib/fichiers.ts` (`separerFichiers`, `nomFichier`) —
jamais réimplémentée dans une page.

### Quel `format` de `PiecesJointes` — la vignette ne répond pas à la même question

| `format` | Où | Pourquoi |
|---|---|---|
| `'vignette'` (défaut) | là où l'on **survole** : listes, fils de messages | signale « il y a une photo » sans casser le rythme de lecture |
| `'grand'` | là où l'on a **demandé à voir** : fil déplié, annonce dépliée, fiche ticket, **et le fil d'évolutions** | l'utilisateur vient de déplier ; lui laisser un timbre-poste de 72 px lui impose un clic de plus pour ce qu'il demande |

🔴 **Le fil d'évolutions est passé de `'vignette'` à `'grand'` le 18/08/2026**, sur
constat à l'écran — ce tableau le rangeait du premier côté, avec un argument juste
mais mal appliqué. Un fil d'Historique ne s'atteint qu'en **dépliant** une carte :
quand on l'a sous les yeux, on a déjà demandé à voir. Et sur un événement de
calendrier, les photos du suivi sont **tout le contenu** (« voici les anomalies
relevées ») — elles étaient réduites à trois timbres-poste là où le même dossier,
en ticket, les montrait en grand avec son compteur « 1 / 3 ».

Le critère ne change pas : *survole-t-on, ou a-t-on demandé à voir ?* C'est son
application à ce cas qui était fausse.

### L'aperçu replié se REPLIE sur l'Historique (18/08/2026)

Quand l'objet ne porte aucune pièce mais que son Historique en porte, la carte
repliée montre celles de l'entrée **la plus récente** — repli calculé côté
serveur par `pieces_ticket_ou_repli` (`routers/tickets/commun.py`), jamais par
le front.

**Why** : un événement de calendrier n'a le plus souvent aucune photo propre, c'est
le suivi qui en apporte. Sa carte restait donc nue là où un ticket illustré montre
sa vignette d'un coup d'œil. La règle du repli existait déjà dans l'autre sens —
ce qu'une entrée diffuse porte ses pièces, « avec repli sur l'objet si elle n'en a
pas » (`flux/tickets.py`) — et elle suit la même logique que le fil, qui **date du
dernier fait, jamais du premier**.

⚠️ **Aucun chargement déclenché** : la fonction ne sert qu'aux écrans dont l'API
livre déjà l'Historique avec l'objet (calendrier : `EvenementRead.evolutions`). Les
**tickets** chargent leurs évolutions à la demande, au dépliage — les réclamer en
liste coûterait une requête par carte. C'est un changement d'API, suivi à part.

Le grand format **ne coûte aucun octet** : il n'existe pas de miniature côté serveur,
les photos sont réduites à 1600 px / JPEG q85 au téléversement, et la vignette
téléchargeait déjà ce fichier-là pour l'afficher en 72 px.

⚠️ **`object-fit: contain` en grand format, jamais `cover`.** Une photo portrait dans
un cadre carré perd ses bords haut et bas — sur un dégât des eaux, précisément ce
qu'on cherchait à montrer. `cover` reste correct pour la vignette, où l'on ne cherche
qu'à signaler la présence d'une image.

### Ce que la visionneuse impose (v2.42.0)

- **Un clic sur une photo n'ouvre jamais un onglet.** L'ancien `<a target="_blank">`
  sortait de la PWA vers le fichier brut, et le retour ramenait sur une page dont
  l'article s'était refermé — le geste le plus coûteux de l'écran, sur mobile surtout.
- **Le verrou de défilement et `Échap` sont des biens du document** : ils passent par
  `poserCouche` (`#lib/couche.ts`), commun à `Modale` et à la visionneuse, dont le
  retrait se lance à la fermeture **et** depuis `onDestroy`. Pourquoi une seule
  porte — une photo ouverte depuis une modale rendait le défilement, et `Échap`
  fermait les deux : l'en-tête du module (#1042). 🔒 `npm run lint:couches`.
- **Le glissement suit le doigt** (#2169) : la photo est déplacée 1:1 pendant le geste
  (`transform` posé sur l'image, jamais une variable CSS héritée), le lâcher décide sur la
  **distance OU la vitesse** — vitesse mesurée à l'instant du lâcher —, la photo part du
  côté où on la pousse et la voisine entre de l'autre ; seule, elle résiste au bord.
  `touch-action: pan-y pinch-zoom` sur le fond : sans lui, le navigateur prenait le geste.
  🔒 `e2e/visionneuse-glissement.spec.ts`.
- `Échap` ferme la couche du dessus, les flèches naviguent, le compteur suit ; cible tactile **≥ 44 px**
  sur le bouton de fermeture — mesurée, pas supposée : la relecture avait laissé
  passer un bouton à 40 px, trouvé en mesurant dans un navigateur à 375×812.

## 12. Visibilité du Kanban (calendrier + widget tableau de bord)

Filtre des colonnes : `if (col.id === 'ag' || col.id === 'cs') return canSeeAG;`

**Glisser une carte** (le conseil seul) : la colonne qui la recevrait se marque PENDANT le
geste, celle d'origine non, et la carte saisie s'efface à demi ; tout s'éteint au lâcher
ou à l'abandon (#2170, 🔒 `e2e/kanban-glissement.spec.ts`).

| Colonne | Locataire | Copropriétaire | CS / Admin |
|---|---|---|---|
| AG | ✗ | ✓ | ✓ |
| CS | ✗ | ✓ | ✓ |
| Syndic | ✓ | ✓ | ✓ |
| Prestataire | ✓ | ✓ | ✓ |
| Terminé | ✓ (affichables) | ✓ (affichables) | ✓ (tout) |
| Annulé | masqué dashboard | masqué dashboard | masqué |

Items non-affichables : masqués aux non-CS/admin, sauf `maintenance_recurrente`.

🔴 **Les colonnes elles-mêmes ne s'écrivent qu'à un endroit** : `KANBAN_COLS`
(`#lib/kanban`), et la brique d'accueil **dérive** `KANBAN_COLS_ACCUEIL`. Elle
recopiait la table jusqu'au 19/09/2026 (#1030) — cinq colonnes au lieu de six,
libellés plus courts, couleurs recopiées à l'identique.

Les deux écarts étaient **légitimes** et ne se déclaraient nulle part. Ils sont
maintenant **dans** la table : `labelCourt` pour l'étroitesse de la brique,
`masqueAccueil` pour « Annulé » (l'accueil montre ce qui avance). La ligne
« masqué dashboard » du tableau ci-dessus est ce que `masqueAccueil` **porte** —
elle ne se code plus à côté.

⚠️ `lint:tables-statuts` était **vert à cause de la divergence** : il cherche
deux tables qui partagent le même ensemble de clés, et une copie **incomplète**
lui échappe. C'est le contrôle du kanban (travail `test-scripts`) qui refuse
désormais une seconde table de colonnes — la même porte que le rangement des
cartes, pas une porte de plus.

### 🔴 12 bis. La forme du kanban condensé (18/09/2026, validé à l'écran)

Variante « K4 », puis la brique du calendrier. Deux décisions, et elles se
tiennent :

- **la brique est celle de `/tickets/kanban`** (ex-`/calendrier/kanban`, qui y redirige) (`ItemKanban.svelte`, depuis
  le 19/09/2026, demandé à l'écran : *« utilise le même UX des briques »*) :
  pastilles de périmètre en haut, titre en gras, type en pied — plus de colonne
  d'icône à gauche. La K4 du 18/09 (icône sur la dernière ligne) est remplacée ;
  c'est l'en-tête d'`ItemKanban` qui fait foi, pas cette ligne (#1161) ;
- **une colonne VIDE se réduit à son titre**, tourné à la verticale
  (`writing-mode: vertical-rl`) : 30 px au lieu de 200, rendus aux colonnes qui
  portent quelque chose. Elle reste **visible** — savoir qu'une étape est vide
  fait partie de la lecture d'un kanban ; c'est le tiret « — » qui ne disait
  rien en occupant la place d'une colonne pleine. **Une seule** colonne vide se
  déplie à la fois (30/09/2026, règle 17 — c'était un `Set` « parce que ce n'est
  pas un accordéon », arbitrage révisé) ;

  🔴 **Le mot « Aucune affaire » se lit DANS le pli** (20/09/2026, demandé à
  l'écran). Il n'apparaissait qu'une fois la colonne dépliée d'un clic : il
  fallait donc agir pour apprendre qu'il n'y a rien à voir. Le `writing-mode`
  de l'en-tête l'oriente avec le titre, et le pli dit alors ce qu'il contient.

- **l'accueil borne ses colonnes à `MAX_CARTES_ACCUEIL`** (trois, `#lib/kanban`),
  avec un report « +N / total ». Le nombre se déclare là et **nulle part
  ailleurs** : il était écrit trois fois dans le composant, et en oublier une
  donne un compteur qui ment sans qu'aucun test ne le voie (`lint:plafond-liste`
  refuse qu'un nombre coupe une liste *et* serve de seuil dans un écran).

  ⚠️ **L'accueil seulement.** `/tickets/kanban` est l'écran dédié : il a la
  place, et y borner les colonnes cacherait ce qu'on vient y chercher.

La grille est donc en **flex** et non en `grid` : une grille donne la même part
à toutes ses colonnes, et c'est exactement ce qu'on ne veut plus.

⚠️ La bande verticale suit la hauteur de la plus haute colonne **par le flex**,
jamais par `height: 100%` sur son en-tête : un pourcentage résolu contre un
parent lui-même étiré tourne en rond, et le navigateur retombe sur la hauteur
de la fenêtre — mesuré, 622 px de colonnes pour 250 px de contenu.


## 13. En-tête de page — `EntetePage.svelte`, une seule écriture

**Ne jamais rendre `<div class="page-header">` à la main.** Le composant porte le
conteneur, le titre (icône + libellé + taille), le retour et la zone d'actions :

```svelte
<EntetePage titre={_pc.titre} icone={_pc.icone || 'newspaper'}>
  {#if $isCS}
    <BoutonNouveau ouvert={showForm} libelle="Nouvelle publication" on:basculer={() => (showForm = true)} />
  {/if}
</EntetePage>
```

🔴 **Le bouton d'ouverture passe par `BoutonNouveau`** — il ne s'écrit plus à la
main (12/09/2026). Il porte le « + », le libellé, et surtout **l'effacement
pendant la saisie** : l'annulation vit à côté d'« Enregistrer », jamais en double
dans l'en-tête (#367, norme du 18/08/2026).

⚠️ **Ce composant a porté la règle INVERSE pendant quatre semaines.** Créé le
16/08 avec la bascule « + … » ⇆ « ✕ Annuler », il n'a pas suivi la révision du
18/08 — que Tickets et Actualités ont appliquée, chacun en la recopiant chez lui.
Trois écritures, dont une périmée, et son en-tête affirmait porter la bonne.
Prestataires, son unique appelant, affichait donc « ✕ Annuler » **même en
édition** — on n'annule pas une création qui n'a pas lieu — jusqu'au signalement
de l'utilisateur. *Une consigne fausse fait lire l'écart comme une décision.*

| Prop | Rôle |
|---|---|
| `titre` | obligatoire |
| `icone` | nom Lucide du catalogue `#lib/icones-svg.json` |
| `retour` | href — affiche `← Retour` **à gauche du titre** |
| `descriptif` | le descriptif **de la page** (`_pc.descriptif`), rendu sous l'en-tête et **au-dessus** des onglets |
| ~~`marge`~~ | **retirée le 17/08/2026** — voir ci-dessous |
| slot par défaut | les actions, **à droite** |

**Disposition, la même partout** : `[retour] titre` à gauche · actions à droite.

🔴 **Le descriptif de page est une prop, pas une ligne de l'écran** (#1369, 27/09/2026).
Douze écrans écrivaient `<div class="page-subtitle">` à la main ; Résidence le posait
**sous** ses onglets, juste au-dessus du descriptif de l'onglet « Fiche », qui portait le
même texte — la phrase se lisait deux fois. Délégations l'écrivait **en dur** : le texte
administrable ne s'y affichait pas. Une phrase par niveau : la page dit ce qu'elle est
(`EntetePage`), l'onglet ce qu'il montre (`BarreOnglets`), et l'onglet **se tait** quand
il répète mot pour mot la page — comparé sans balisage, les deux étant administrables.
🔒 `lint:entetes` (motif 4, composants compris) · `e2e/descriptif-page.spec.ts`.

⚠️ **Vérifier que l'icône existe** dans `#lib/icones-svg.json` : `Icon` retombe
**silencieusement** sur `help-circle` pour un nom inconnu. `message-square-plus`
n'existe pas et aurait affiché un point d'interrogation sans qu'aucun contrôle ne
le dise (constaté le 15/08/2026). Depuis le 24/09/2026, `npm run lint:icones` le
dit : il a trouvé `database`, affiché en « ? » depuis v2.19.0 (#1045).

**Garde-fou** : `npm run lint:entetes` (job `build-frontend`) refuse un
`class="page-header"` écrit à la main, une redéfinition locale de `.page-header`,
et un `<h1>` portant `font-size` en ligne. Les exceptions sont **nommées avec leur
raison** dans le script, et le contrôle échoue si l'une devient inutile.

**Dette soldée le 17/08/2026 — la marge d'en-tête vaut `1.5rem`, sans exception.**

`marge` existait parce que **six** écrans divergeaient : `0` (FAQ), `.5rem`
(espace CS, prestataires), `.75rem` (délégations, résidence), `1rem` (calendrier),
contre `1.5rem` partout ailleurs. Centraliser les valeurs les avait rendues
explicites **sans les réduire** — la dette était nommée ici, et elle a duré.

Le symptôme se voyait : en passant d'`/actualites` à `/calendrier`, le titre et le
bouton **sautaient** de quelques pixels, alors que les deux pages utilisent le même
composant (#372). Arbitré par l'utilisateur : la valeur du plus grand nombre gagne.

**La prop n'existe plus.** C'est le point important : la laisser en place aurait
invité la septième valeur. Un écran qui aurait vraiment besoin d'autre chose doit
d'abord expliquer pourquoi lui — pas recevoir une prop qui rouvre les six.

⚠️ Le retrait a fait **échouer `lint:entetes`**, dont le cas zéro exige que
`EntetePage` expose ses props connues. C'est voulu : son message dit « le contrat a
changé — mettre ce contrôle à jour ». Un garde-fou qui n'aurait rien dit aurait
laissé passer une prop disparue, et donc laissé le contrôle vérifier un contrat
imaginaire.

> **La leçon, générale** : nommer une divergence ne la corrige pas. Centraliser
> six valeurs dans une prop les rend lisibles et **pérennes**. Tant que le
> mécanisme d'exception existe, l'exception se reproduit.

**Pages de détail** (`tickets/[id]`, `sondages/[id]`) : elles n'ont **pas**
d'en-tête de page — leur `<h1>` est le titre de l'objet. Ne pas les convertir
mécaniquement : ce qu'il faut y mettre est instruit dans #365.

🔴 **Le lien d'une affaire rend SA CARTE, dépliée** (15/10/2026, signalé à l'écran :
*« affichée d'une manière différente du fil d'actualité ou de la page »*).
`/tickets/[id]` rendait une fiche à part — en-tête, boutons d'état, Historique ; il
rend désormais `ListeTickets` sur une liste d'UNE affaire, dépliée d'office, avec
les gestes de la liste (`#lib/affaires-en-liste`, la seule écriture des gestes, que
la page Affaires emploie aussi). Ce qui lui reste propre : le fil de MESSAGES dessous
(les notifications pointent `#msg-…`), et un `<h1 class="sr-only">` — le titre de la
carte est un bouton qui la plie, pas un intitulé. Un objet, un rendu : une fiche qui
se lit autrement que sa carte est une divergence, pas une page de détail.
🔒 `e2e/lien-affaire-depliee.spec.ts`.

**Leur colonne de lecture : `.colonne-lecture`** (`normes.css`, 720 px), posée
sur **chaque** bloc — la carte, le fil de messages —, jamais une largeur écrite
par la page sur la classe d'un composant enfant. C'est ce qui s'était produit : la règle visait `.messages`,
l'extraction de `FilMessagesTicket` l'a rendue morte, et la barre « Répondre »
s'étalait seule jusqu'au bord de l'écran (01/10/2026, signalé à l'écran).
🔒 `e2e/transferts-verses.spec.ts` mesure que le lien direct n'a qu'un bord droit.

## 13 bis. 🔴 LE MODE SE LIT SUR L'ICÔNE QUI L'A OUVERT

**Corrigé le 18/08/2026, le soir même où la règle inverse avait été posée.**
Ce paragraphe disait : *« tout formulaire porte un titre, et c'est lui qui dit
le mode »*. Le diagnostic d'origine était bon — le mode ne se lisait nulle part,
signalé ainsi : *« on ne sait pas si on est en mode édition, en mode suivi »* —
mais le remède était mauvais, et l'écran l'a dit :

> « les titres d'état je ne trouve pas ça beau : je mettrais l'icône concernée
>   en plus gros ou inversée pour supprimer ce pseudo état qui éloigne du titre »

Un titre au-dessus du formulaire ajoute un **second en-tête** sous celui de la
carte : il repousse le contenu et éloigne le formulaire de l'objet auquel il se
rapporte. Le bon endroit pour dire « vous êtes en train de commenter » n'est pas
au-dessus du formulaire, c'est **sur l'icône qui l'a ouvert** — elle est déjà là,
déjà regardée, et son inversion se lit sans être lue.

### La règle

| Où | Ce qui dit le mode |
|---|---|
| formulaire **encadré** (création) | son titre : c'est l'en-tête de SA carte, pas un doublon |
| formulaire **dans la carte d'un objet** | l'icône qui l'a ouvert, **inversée** |

```svelte
<button class="btn-icon" aria-pressed={mode === 'evolution'} …>🔄</button>
<button class="btn-icon" aria-pressed={mode === 'edition'} …>✏️</button>
```

Le style vit dans `styles/composants.css`, une seule fois : fond plein en couleur primaire,
glyphe blanc, `scale(1.15)`. ⚠️ **Un simple changement de teinte ne suffit pas** :
il ne se distinguerait pas du survol, et l'on ne saurait plus si l'icône est
active ou seulement pointée.

⚠️ **`aria-pressed`, et non une classe.** L'état est alors annoncé par les
lecteurs d'écran en même temps qu'il se voit, aucun écran n'a de classe de plus à
penser — et un bouton bascule doit le porter de toute façon.

⚠️ **Le titre ne disparaît pas, il devient invisible** : `FormulaireCreation` le
passe en `aria-label` sur le groupe. Qui ne voit pas l'icône entend toujours
« Modifier le commentaire » en entrant dans le formulaire.

⚠️ `encadre` garde son autre rôle : à `false`, pas de carte imbriquée — deux
bordures pour un seul objet, c'est la « carte dans la carte » de #425. C'est le
composant qui décide, jamais l'écran.

## 14. Formulaire de création — `FormulaireCreation.svelte`, une boîte dans la page

**Un seul paradigme sur tout le site : la boîte dans la page.** Les actualités
sont le modèle, désigné par l'utilisateur.

```svelte
<EntetePage titre={_pc.titre} icone={_pc.icone} alignerSaisie={showForm}>
  {#if $isCS}
    <button class="btn btn-primary page-header-btn" on:click={() => (showForm = !showForm)}>
      {showForm ? '✕ Annuler' : '+ Nouvelle publication'}
    </button>
  {/if}
</EntetePage>

{#if showForm}
  <FormulaireCreation titre="Nouvelle publication">
    <form on:submit|preventDefault={creer}> … </form>
  </FormulaireCreation>
{/if}
```

**Ce qui était faux avant le 15/08/2026** (#367), et que l'utilisateur a dû
signaler **trois fois** :

- **trois paradigmes** pour la même intention — boîte (actualités, sondages),
  modale (calendrier, prestataires, accès & badges, fiche sondage), page dédiée
  (nouveau ticket) ;
- le bouton d'annulation **excentré** : il se posait au bord droit de l'ÉCRAN
  alors que la boîte s'arrête à 720 px ;
- sur le calendrier, **deux** commandes d'annulation — la croix de la modale et
  le bouton d'en-tête, ce dernier sous l'overlay, visible et inutilisable.

### Les trois règles

1. **La commande d'annulation reste dans l'en-tête**, où le bouton d'ouverture
   bascule en « ✕ Annuler ». Ne PAS en ajouter une seconde dans la boîte.

   > ⚠️ **Périmé** : depuis le 18/08/2026, l'annulation vit au pied du formulaire et
   > `BoutonNouveau` s'efface pendant la saisie (§13, arbitrage n° 31) ; l'exemple ci-dessus
   > aussi. Vérifié dans `BoutonNouveau.svelte` le 18/10/2026.

2. **`alignerSaisie={showForm}` sur `EntetePage`** dès qu'un formulaire s'ouvre
   dans la page — sans lui le bouton flotte loin de ce qu'il annule.
3. **Jamais de modale pour un formulaire de CRÉATION.** Les modales restent
   légitimes pour une confirmation, un téléversement ponctuel, la visionneuse —
   — mais **plus pour l'édition** d'un objet : voir §14 bis (06/09/2026).

### 🔴 14 bis. CRÉER ET CORRIGER EMPLOIENT LA MÊME BOÎTE DANS LA PAGE (06/09/2026)

Arbitré à l'écran : *« la boîte d'édition n'est pas standard à l'UX, elle
apparaît dans une fenêtre indépendante au lieu de la fenêtre principale […]
comme le reste du site, avec un UX standard, pas de spécifique. »*

| Geste | Format |
|---|---|
| **Créer** | la **boîte dans la page** — `FormulaireCreation`, §14 ci-dessus |
| **Corriger** un objet existant | **la même boîte**, au même endroit |

Le choix se fait dans **`CadreFormulaire`**, et nulle part ailleurs : huit
formulaires le traversent.

## ⚠️ CE PARAGRAPHE DISAIT L'INVERSE PENDANT SEPT JOURS

Du 30/08 au 06/09/2026, il énonçait : *« la modale est le format standard
d'édition »*, arbitré à l'écran lui aussi, avec un raisonnement qui se tenait —
« une édition interrompt une lecture ; déplier un formulaire au milieu d'une
liste déplace tout ce qui est en dessous ».

🔴 **Ce raisonnement n'a pas été réfuté, il a été tranché autrement** : une boîte
qui flotte par-dessus la page est un **paradigme de plus**, et c'est exactement
ce que #367 avait éliminé pour la création (il y en avait trois). Le produit a
préféré un seul format pour les deux gestes à deux formats bien motivés.

L'argument du décalage de liste, lui, avait **déjà** sa réponse :
`FormulaireCreation` s'amène lui-même à l'écran depuis le 29/08 — c'est
l'édition, dont le geste part d'une carte, qui en a le plus besoin.

⚠️ **Ce que ce second renversement ne remet PAS en cause** : les trois constats
de #367 restent vrais — pas de **double commande** d'annulation, pas de bouton
**excentré**, et surtout pas plusieurs paradigmes pour une même intention. On
revient simplement à « un format pour tout ».

🔒 **Le garde-fou a fait son travail avant de changer de forme.** Le cas zéro de
`lint:formulaires` exigeait de trouver `Modale` dans le `this={…}` de
`CadreFormulaire` : il a **refusé le lot qui appliquait la décision**, au lieu de
passer au vert en mesurant moins. Il vérifie désormais l'inverse — que la boîte
est rendue, et qu'aucune `Modale` ne revient par la porte de derrière.

⚠️ Les modales restent légitimes pour ce qui n'est pas un formulaire d'entité :
confirmation, **saisie qui accompagne un geste**, téléversement ponctuel,
visionneuse, écrans d'administration.

### La saisie qui accompagne un geste — `Saisie.svelte` (tranché le 14/09/2026, #931)

Signaler un contenu au conseil syndical demande un **motif**. Ce motif ne crée
aucun objet qu'on retrouvera dans une liste, et n'en corrige aucun : il
**accompagne un geste**, exactement comme une confirmation — dont il n'est que la
version qui pose une question ouverte au lieu d'une question fermée.

🔴 **Il n'y a donc pas de troisième forme à inventer**, et c'est ce que le ticket
cherchait. `Confirmation.svelte` est déployé seize fois, c'est une fenêtre, et il
répond déjà à *« que fait-on d'une question posée avant un geste ? »*. Les deux
règles qui interdisent la fenêtre — la création s'écrit dans la page (#367), la
correction dans la carte (§14 ter) — parlent l'une et l'autre d'un **objet** :
aucune ne recouvre ce cas. La règle la plus déployée l'emporte, et il n'y avait
qu'à la nommer.

⚠️ **Ce qui ferait basculer de l'autre côté** : si le motif devenait un champ de
l'objet signalé — modifiable, relisible, porté par une fiche — il cesserait
d'accompagner le geste pour devenir une **entité**, et la règle de la carte
reprendrait la main. Ce n'est pas le cas : le motif part au conseil syndical et
ne revient pas à l'écran.

⚠️ **Ouvrir le motif DANS la rangée a été écarté pour une raison mesurée**, pas
par goût : `signaler()` cesserait d'être un appel impératif et demanderait un
état d'ouverture **par ligne**, dans `Reponses` et dans chaque liste qui
l'emploie — c'est exactement l'échafaudage que `confirmer()` a retiré à seize
appels. On ne réintroduit pas pour un geste ce qu'on a supprimé pour seize.

### 🔴 OÙ SE POSE LE CADRE : **là où le geste est connu** (30/08/2026, calendrier)

La question s'est posée au troisième écran, et elle se reposera aux suivants —
elle est donc tranchée ici plutôt qu'à chaque conversion.

| Le composant de formulaire reçoit-il le geste ? | Qui pose le cadre |
|---|---|
| **oui** (`modeEdition` est une de ses propriétés) | **le composant** |
| **non** (il ne connaît que les champs) | **l'écran appelant** |

`FormulaireContrat` écrit l'inverse dans son en-tête — *« mettre le cadre ici
obligerait le composant à connaître le geste »* — et **c'est juste pour lui** :
il ne le reçoit pas. `FormulaireTicket`, si — comme le faisait le formulaire
d'événement de #432, supprimé avec #1092. La règle générale
recouvre donc les deux cas sans en contredire aucun.

⚠️ **Ce qu'il en coûte de choisir l'autre.** Poser le cadre dans la page oblige à
deux branches `{#if}` montant le **même** formulaire avec les mêmes propriétés —
seize pour l'événement, dont quatre liaisons bidirectionnelles que `{...props}`
ne répand pas dans le mode legacy de Svelte 5 (`export let`, `$:`). Deux copies qui divergent au premier champ ajouté, c'est-à-dire
la duplication que l'extraction du composant avait supprimée.

**Dans le mode legacy de Svelte 5** — celui du projet (`svelte ^5`, `export let`,
`$:`) ; ce n'est pas du Svelte 4 —, **la forme d'origine, qui n'écrit le corps
qu'une fois, était :**

```svelte
<svelte:component
	this={modeEdition ? Modale : FormulaireCreation}
	titre={titreCadre}
	{...(modeEdition ? { edition: true } : {})}
	on:fermer={() => dispatch('annule')}
>
```

⚠️ `<svelte:component>` n'est déprécié qu'en **mode runes**. Si le projet y passe,
la forme recommandée est un composant dynamique — `{@const Cadre = modeEdition ?
Modale : FormulaireCreation}` puis `<Cadre … />`. Depuis §14 bis, aucun écran
n'écrit plus ce choix : il vit dans `CadreFormulaire`, seul endroit où il se
tranche.

🔒 **Nommer `Modale` DANS le `this={…}` fait partie du geste** : c'est ce que
`lint:formulaires` lit. Un cadre choisi dans une variable (`const cadre = …`)
compile aussi bien et sort la modale du champ du contrôle.

**Garde-fou** : `npm run lint:formulaires` (job `build-frontend`). Il refuse un
cadre `card largeur-saisie` enveloppant un `<form>`, et toute modale portant un
formulaire **sans se déclarer `edition`**. Il a trouvé **deux écrans que l'audit
manuel avait manqués**.

🔒 **Son périmètre a été étendu le 30/08/2026, et c'était le préalable.** Il ne
lisait que `routes/`, alors que le cadre se pose dans le **composant** dès que
celui-ci connaît le geste : chaque conversion faisait donc sortir la modale de son
champ — *convertir revenait à se désarmer*. Il lit désormais aussi
`lib/components/`, et il reconnaît la modale montée par `<svelte:component>`.

✅ **`prestataires` est traité** : le fichier fait **822 lignes** (contre 2 182)
et ne porte **plus aucune** `<Modale>`. Ce paragraphe l'annonçait encore comme
« reste à traiter », avec quatre formulaires en modale — deux chiffres et un
constat, tous périmés.

⚠️ Ce qui reste, et qui n'était pas la modale : le périmètre y est une **chaîne**
dans un `<select>` là où `PerimetrePicker` travaille sur un tableau. C'est un
changement de contrat, pas un remplacement de composant — et c'est la seule
partie de ce paragraphe qui était encore vraie.

### 🔴 14 ter. LA CORRECTION S'OUVRE À LA PLACE DE L'OBJET (10/09/2026)

Arbitré à l'écran, en une question : *« la position de la fenêtre d'édition
est-elle standard ? avant à la fin, maintenant au début — le standard n'est-il
pas sur la position courante ? »*

Sur les contrats, la boîte d'édition s'ouvrait d'abord **en bas de page**, puis
**en haut** après une première correction. Les deux sont au mauvais endroit : sur
une liste de vingt éléments, l'un comme l'autre déplacent l'utilisateur loin de
ce qu'il édite. La `cle` de `FormulaireCreation` le ramenait bien à l'écran —
mais à l'écran du **formulaire**, pas à sa place dans la liste.

| Geste | Où la boîte s'ouvre |
|---|---|
| **Créer** | en tête de liste — elle ne corrige rien, elle n'a pas de place à occuper |
| **Corriger** | **dans la carte**, à la place de son CORPS — l'en-tête reste, avec son titre et ses actions |

⚠️ **§14 bis n'est pas remis en cause** : c'est toujours LA MÊME BOÎTE — même
composant, même format. Ce qui change est sa **position**, qui suit désormais
l'objet corrigé. « La même boîte » ne voulait jamais dire « le même endroit du
DOM », et c'est ce raccourci qui a produit les deux erreurs.

🔴 **Trois positions essayées en une journée, dont deux fausses.** La leçon n'est
pas qu'il fallait deviner : c'est qu'une position de formulaire se juge **sur une
liste longue**, jamais sur un écran de trois éléments où tout est visible à la
fois.

🔴 **DÉPLACER un rendu, c'est aussi RETIRER l'ancien** — et ce second geste s'est
oublié le jour même. La correction a déménagé dans la carte le matin ; le bloc de
tête de liste, lui, est resté ouvert sur `contratFormOuvert || editContratId`.
Résultat signalé à l'écran l'après-midi : *« plusieurs contrats sont ouverts en
édition simultanément »* — deux boîtes « Modifier le contrat » à la fois, et la
`cle` de celle du haut qui ramenait la page en haut.

⚠️ **`lint:geste-edition` ne pouvait pas le voir, et c'est l'extraction qui l'a
aveuglé** : sa règle B compte les rendus d'un formulaire **fichier par fichier**,
et le second venait d'être déplacé dans un second fichier. La **règle C** couvre
désormais le cas sans dépendre du découpage : *un identifiant d'édition
(`editXxxId`) ne peut pas à la fois ouvrir un formulaire dans l'écran et être
confié à un composant enfant* — les deux rendus s'affichent alors ensemble.

🔴 **QUATRIÈME position, et la bonne** — désignée par l'utilisateur le 10/09/2026 :
*« l'affaire modifiée passe en premier ! prends exemple sur tickets »*. Remplacer
la carte **entière** effaçait la ligne du contrat, et `FormulaireCreation`
ramenait sa boîte en haut de la fenêtre dès qu'elle n'y tenait pas : l'objet
corrigé quittait sa place dans la liste.

Le motif des tickets ne déplace **rien** : la carte reste, son **en-tête** reste —
titre, tags, date, actions — et seul le **corps** cède la place au formulaire, en
`encadre={false}` pour ne pas poser une carte dans une carte. Le mode se lit sur
le crayon (§13 bis), et **aucune `cle` n'est nécessaire** : rien n'a bougé, il n'y
a rien à ramener à l'écran.

⚠️ **Ce composant existait DEUX fois** — `AnnonceCard` et `CarteActualite`
portent tous deux une prop `formulaireOuvert` et un `<slot name="formulaire" />`
qui font exactement cela, depuis des semaines. Trois positions fausses ont été
essayées sans que je les ouvre : la question « où mettre la boîte ? » avait déjà
sa réponse dans le produit. C'est la **sixième** fois — voir la mémoire
`project_le_composant_existait_deja`. Le réflexe reste le même : chercher la
**notion** (« corriger un objet d'une liste »), jamais le nom de l'écran.

🔒 **Depuis le 02/10/2026 (#1539), ce squelette a UN composant : `CarteModifiable`**
— conteneur, `EnteteCarte`, 🔗 ✏️ 📦 (↩️ aux Archives, #1538), corps qui cède la place à
`FormulaireCreation` (`encadre={false}`), titre inerte pendant la correction.
`CarteContrat` et `CartePrestataire` le recopiaient l'une sur l'autre ; une carte
neuve qui se corrige en place le monte et remplit ses emplacements (`tags`,
`apercu`, `gestes`, `edition`, `detail`). Qui RETIRE sans corriger — le gestionnaire
du site devant un avis (#2075) — se dit par `peutArchiver`, qui ressort par
`peutRestaurer` (absents, ils valent `peutModifier`) ; ce qui se fait de plus aux
Archives (🗑️ d'un avis) va dans `gestes-archive`. ⚠️ `AnnonceCard` et `CarteActualite`
portent encore leur propre `formulaireOuvert` : même notion, pas encore migrée.

🔴 **Et ce n'était toujours pas fini : le formulaire DÉFILAIT.** Troisième
signalement du même symptôme — *« le contrat édité remonte en haut »* — alors que
la carte, elle, ne bougeait plus d'une ligne. Ce n'était pas un déplacement dans
la liste : `FormulaireCreation` appelait `ramener()` **à chaque montage**, sans
condition. Un formulaire ouvert dans la carte d'un objet, en bas de la fenêtre,
dépassait la bande visible de quelques pixels et se faisait ramener en haut de
l'écran — en emportant sa carte.

**La règle, désormais : `cle` ne distingue plus seulement deux objets, elle
DEMANDE le défilement.** Sans `cle`, le composant ne défile jamais.

| Le formulaire s'ouvre… | `cle` | Défile ? |
|---|---|---|
| dans la carte de l'objet corrigé | non | **non** — ce qu'on regarde est déjà là |
| en tête de page, geste juste au-dessus | non | **non** |
| ailleurs que là où l'on a cliqué (liste longue, tableau) | **oui** | oui |

⚠️ **L'intention était écrite dans le fichier même**, à dix lignes de l'appel
fautif : *« un formulaire qui s'ouvre sous les yeux n'a pas à faire sauter la
page »*. Le code ne testait que la **position**, jamais la raison d'être là — et
la position seule ne distingue pas « ouvert loin du geste » de « ouvert un peu
bas ». C'est le motif que ce dépôt connaît le mieux : *la règle est écrite, et
elle n'est pas appliquée*.

🔒 `lint:geste-edition` **règle D** : aucun appel à `ramener()` hors de la garde
`cle !== undefined`. Vérifié sur la version fautive — elle la refuse.

📐 **Ce qui a permis de trancher, après trois corrections à l'aveugle** : le vrai
composant monté dans une **route jetable**, avec soixante cartes et un
`Element.prototype.scrollIntoView` instrumenté. Le raisonnement disait « rien ne
peut bouger » ; le relevé a montré l'appel, à la ligne près. Même leçon que
`project_flex_enroulement_avant_compression` — une reproduction approximative ne
reproduit rien.

### La règle en une phrase — et l'audit qui la fait tenir (10/09/2026, #889)

> **La boîte s'ouvre là où est le geste.**

| Geste | Où la boîte s'ouvre |
|---|---|
| **Créer** depuis un bouton de page | en tête de liste — le geste est là |
| **Créer sous un objet** (« ＋ sous-périmètre ») | **dans cet objet** — le geste y est aussi |
| **Corriger** un objet | **dans sa carte, à la place de son corps** ; l'en-tête reste |
| **Commenter** / faire évoluer | idem (`EvolForm`, déjà conforme) |

⚠️ Le « ＋ » d'un nœud n'est **pas** une entorse à « créer s'ouvre en tête » :
c'est la même règle. Le bouton de la barre ouvre en tête parce qu'il y est.

🔒 **`lint:geste-edition` règle E** : `<Modale edition>` est refusée. Le produit
distinguait déjà, par cette propriété, la fenêtre de **correction** de celle de
**confirmation** ou d'**aperçu** — le contrôle s'appuie sur la distinction qui
existe plutôt que d'en inventer une, et les confirmations restent légitimes.

Les **sept** écrans qui en portent encore une sont déclarés dans le contrôle avec
leur motif et le ticket #889 : la dette est nommée, elle ne peut plus grandir, et
une déclaration qui ne sert plus fait échouer.

⚠️ **Cinq d'entre eux ne sont pas des corrections mais des GESTES** (valider un
compte, terminer un bail, noter un prestataire) ou un **sous-écran** entier. La
règle parle de *corriger* : l'étendre à un geste court est une décision
d'interface qui se prend devant l'écran. Ne pas la trancher dans un fichier —
c'est ce qui a coûté trois MEP le même jour.

## 15. DROITS — qui peut éditer, qui peut commenter (18/08/2026)

| Geste | Qui |
|---|---|
| **✏️ éditer** le contenu | l'auteur · le « saisi pour » · l'admin |
| **🔄 commenter** et faire avancer le workflow | les mêmes **+ le conseil syndical** |

> « Seul l'auteur peut l'éditer ou le commenter, avec l'admin (en cas de Pb),
>   mais aussi le CS peut commenter, pas éditer »

🔴 **« Saisi pour » compte comme auteur**, et c'est la raison d'être du champ :
un membre du CS qui dépose un ticket au nom d'un résident ne le dépossède pas de
sa demande. Avant, ce résident était le **seul** à ne pas pouvoir corriger ce qui
parle de lui — pendant que n'importe quel membre du CS le pouvait.

Les deux règles vivent dans `auth/deps.py` (`peut_editer`, `peut_commenter`),
jamais dans un routeur ni dans un écran. `test_droits_editer_commenter.py` les
verrouille.

⚠️ **L'écran doit dire la même chose que le serveur, ni plus ni moins.** Un
bouton affiché plus largement que le droit produit un 403 sur un geste que
l'interface a elle-même proposé ; plus étroitement, il rend une capacité
introuvable. Les deux sont arrivés le même jour dans `RubriqueHistorique`.

### 🔴 Et le NOM AFFICHÉ est celui du propriétaire (21/09/2026, #1104)

Le pendant du droit ci-dessus, et il a mis six jours à le rejoindre. Un objet
« Saisi pour » appartient à celui **pour qui** il a été ouvert :

| Ce qu'on demande | La fonction, dans `#lib/saisi-pour` |
|---|---|
| le nom que l'écran **affiche** | `nomProprietaire(objet)` |
| le nom que la case « Envoyer une copie à … » **annonce** | `nomCopie(objet, saisie?)` |

Elles rendent le même nom dans le cas courant, et ce sont **deux questions** :
`nomCopie` tient compte d'une saisie **en cours** — elle doit annoncer ce qui
partira au prochain clic —, ce qu'un affichage de liste n'a pas à connaître.
Jamais `objet.auteur_nom` dans un écran : c'est le rédacteur, et l'arbitrage du
12/09 dit que le « Saisi pour » s'y substitue.

⚠️ **Le même composant employait les deux.** `CarteTicket` appelait déjà
`nomCopie` pour la copie, et affichait `auteur_nom` brut à trois lignes de là :
un écran, deux noms, et celui qu'on lit était le mauvais. La FAQ servie aux
résidents promettait pourtant l'inverse.

🔒 `npm run lint:nom-proprietaire` (CI depuis le 21/09/2026). Il lit la liste des
types porteurs **dans `types.ts`** — ceux qui héritent de `PorteSaisiPourLu` —,
jamais une liste recopiée qui divergerait au premier type ajouté. Deux listes
déclarées, qui ne font pas la même chose : `PORTEURS_NON_TYPES` **étend** le
contrôle aux écrans dont la prop est `any`, `EXCEPTIONS` **autorise** la seule
phrase du site qui nomme légitimement l'auteur — et elle porte sur une **ligne**,
pas sur un fichier.

Côté serveur, `proprietaire_nom` vit dans `SaisiPourSortie`, dont les trois
lectures héritent, et les trois routeurs le posent par `noms_derives` :
`api/tests/test_proprietaire_expose.py`.
### 🔴 Un libellé NOMME l'objet, et le nom vient de sa déclaration (21/09/2026, #1107)

Le modèle s'appelle `Ticket`, l'écran dit **« Affaire »** — et **« Actualité »** pour
sa catégorie (le modèle `Publication` a été supprimé le 30/09/2026, #1177). Même distinction que `TicketEvolution`
/ « Suite » : le modèle garde son nom, l'écran parle français.

| Ce qu'on écrit | Où le mot se lit |
|---|---|
| le bouton de création | `ENTITE.libelleNouveau` |
| le titre de la boîte d'édition | `ENTITE.libelleModifier` |
| un toast, une confirmation, un titre de section | `ENTITE.libelle` |

`#lib/entites/<entité>.ts` — jamais réécrit dans un écran.

⚠️ **Le renommage v2.1.0 a traité les écrans, la FAQ, le README et le manuel, et
PAS les verbes d'action.** Le mot de code avait donc fui jusqu'au bouton :
« + Nouvelle Publication » sur la page *Actualités*, « Signaler un problème » sur
*Affaires*, « Ticket supprimé » dans un toast. Le ticket en citait trois ; un
relevé mécanique en a trouvé **vingt**, dans seize fichiers.

🔴 Et la source du bon mot **existait**, en affirmant le mauvais :
`EntiteDeclaree.libelle` se décrit comme « le nom de l'entité à l'écran » et
valait `'Publication'`. C'est la 8ᵉ fois que la chose existait déjà
(`project_le_composant_existait_deja`).

🔒 `npm run lint:vocabulaire-ecran` (CI depuis le 21/09/2026). La liste des mots
surveillés se **lit** dans `entites/` (`motDeCode`) : un troisième renommage
n'ajoutera qu'une ligne à sa déclaration. Il ne cherche le mot que dans les
**libellés composés pour être affichés**, et ignore ce qui est interpolé ou lu
d'une constante — sans quoi il refuserait le correctif lui-même.

⚠️ Une seule exception déclarée : « **Options de publication** », où
« publication » est l'**acte** de publier et non l'objet — la section sert aussi
aux affaires et aux événements.

Le pendant serveur est `api/tests/test_vocabulaire_affaire.py`, qui lit les
sources de texte **servi** (pages.ts, FAQ, courriels, README, manuel) et déclare
ne pas lire les `.svelte`. Les deux ensemble couvrent ce qu'un résident lit.

## 16. WORKFLOW & ARCHIVAGE — ce qui a des étapes, et ce qui se range tout seul

🔴 **Trois questions distinctes**, que le produit a confondues jusqu'au 18/08/2026 :

| Question | Réponse |
|---|---|
| l'objet a-t-il des **étapes ordonnées franchies par plusieurs** ? | alors il a un **workflow** (section 3) |
| ces mouvements doivent-ils **laisser une trace** ? | c'est une **AUTRE** décision — l'annonce a cinq états et aucun fil |
| quand disparaît-il de la liste ? | **calculé**, jamais choisi — voir plus bas |

⚠️ Le test n'est pas « y a-t-il un champ `statut` ? ». Trois entités en portent un
et une seule a un workflow tracé. Confondre les deux fait importer un
`RubriqueHistorique` par réflexe sur un objet qui n'a rien à raconter.

### L'archivage se CALCULE, il ne se choisit pas

**30 jours** après l'entrée dans un état **terminal** — mesuré sur
`statut_change_le`, **jamais** sur `mis_a_jour_le`. *Annulé* disparaît
**immédiatement**.

🔴 **« Aucun bouton 📦 » est RÉVISÉ le 24/09/2026 pour les affaires et les
actualités** : l'administrateur y supprimait définitivement depuis la liste, d'un
clic (« c'est une suppression ou pas ? »). Le 🗑️ y cède la place à 📦 — geste du
conseil, `archive_manuel` — et ne reste qu'aux Archives (§8). Le calcul
ci-dessous continue de s'appliquer ; le geste s'y ajoute, il ne le remplace pas.

⚠️ `mis_a_jour_le` paraît équivalent et ne l'est pas : corriger une faute de
frappe sur un objet conclu **repousserait son archivage d'un mois**, à chaque
retouche. `Publication` portait `statut_change_le` pour exactement cette raison,
et les tickets mesuraient encore sur `mis_a_jour_le` au 18/08.

⚠️ Un bouton d'archivage crée **deux notions pour la même chose** — celle qu'on
pose et celle qui arrive — libres de se contredire dès qu'on rouvre l'objet.
L'archivage n'est pas une étape : c'est une conséquence du temps.

🔴 **Calculé côté SERVEUR**, transporté dans un champ `archivee`. Jamais
recalculé par un écran : sinon la liste et l'Historique tranchent différemment,
et c'est le bug du 17/07/2026 sur les actualités — un élément visible dans une
vue et pas dans l'autre.

🔴 **Une actualité n'a pas de workflow, et c'est définitif** (ré-arbitré le
18/08/2026, après l'avoir ouvert la veille). Elle n'a pas d'étapes de vie : elle
est publiée, puis bascule dans l'Historique au bout de son délai. « En cours »,
« Résolu », « Annulé » sont le vocabulaire d'un **ticket**, et les emprunter
faisait ressembler une annonce à un dossier suivi. Son Publié/Brouillon est une
décision de **diffusion**, et vit en section 2.

> ⚠️ **Révisé le 10/10/2026** : une actualité a un **suivi optionnel** — Ouvert · Résolu ·
> Annulé (`ETATS_SUIVI_ACTUALITE`, v2.131.0) — arbitrage n° 26.

La déclaration le dit (`sansObjet`), et c'est elle qui l'impose : la section
disparaît de la création, de l'édition **et** de l'Historique — dans ce dernier,
parce que la liste d'états passée à `EvolForm` est **vide**, pas parce qu'une
condition en dur le décide.

⚠️ **Conséquence en cascade** : l'archivage manuel d'une actualité exigeait l'état
« Résolu ». Sans workflow, il ne pouvait plus être atteint — l'icône 📦 a donc
disparu avec lui. L'archivage **automatique**, lui, reste.

🔴 **REVIREMENT — une PETITE ANNONCE A un workflow** (arbitré le 18/08/2026, le
soir même où ce paragraphe affirmait le contraire). Cinq états : **En cours ·
Réservé · Vendu · Donné · Annulé**.

Ce paragraphe disait : *« l'annonce a un état, mais il lui manque la seconde
moitié de la question — qui l'y a mis ; il n'y a qu'un acteur »*. Le
raisonnement était cohérent et **faux** : il regardait **qui agit**, quand la
question de la section 3 est d'abord **où en est l'objet**. Un vendeur qui a
réservé, vendu ou renoncé a bien un cycle, et ses voisins ont besoin de le lire.

⚠️ **Ce que le revirement ne remet pas en cause** : il n'y a toujours pas de fil
d'évolutions sur une annonce. **Déclarer un workflow et le TRACER sont deux
décisions distinctes** — la seconde n'a pas été demandée. Ne pas les confondre
est ce qui évite d'importer un `RubriqueHistorique` par réflexe.

⚠️ **L'archivage n'est PAS un état.** Une annonce conclue reste un mois puis
bascule dans un Historique replié. C'est une conséquence du temps, pas une étape
qu'on choisit : elle se **calcule** (`est_archivee`), et en faire une sixième
pastille donnerait deux notions pour la même chose — celle qu'on pose et celle
qui arrive. Même règle que les actualités.

🔴 **La leçon de méthode, elle, tient** : c'est la deuxième fois en deux jours
que l'écran réfute le papier (« une actualité n'a pas de workflow » allait dans
l'autre sens). Il ne faut pas en conclure qu'il faut moins déclarer — **c'est la
déclaration qui rend le désaccord visible et corrigeable en un seul endroit**.
Sans elle, les deux raisonnements auraient coexisté dans deux écrans.

**Why (16/08/2026)** : la section finale s'appelait « État », terme qui mélangeait
l'étape de vie et la mise à disposition. Le Suivi Kanban s'y trouvait alors qu'il
dit *où en est le travail*, pas *qui le voit*. Termes retenus par l'utilisateur
après une première proposition inexacte de ma part.



## 17. MOUVEMENT ET RETOUR AU TOUCHER — la règle du site (24/09/2026)

Essayé sur les Petites annonces (v2.44.0, R5), **généralisé** le même jour à la
demande de l'utilisateur. Une seule écriture chacun, dans la charte :

| Quoi | Règle | Où |
|---|---|---|
| jetons | `--ease-out` (courbe de sortie marquée), `--duree-geste` 120 ms, `--duree-apparition` 200 ms. Un SCRIPT n'en écrit pas non plus : il pose une classe ou une valeur, le CSS anime, et il attend `finDesAnimations` (`#lib/mouvement`, avec `mouvementReduit`) — jamais `transitionend`, muet quand la transition ne démarre pas (#2168). **Aucune durée écrite** : un survol, un appui, un changement de couleur → `var(--duree-geste)` (courbe par défaut ; `--ease-out` si `transform`) ; ce qui ENTRE → `var(--duree-apparition) var(--ease-out)`, cascade par `var(--delay, 0s)` posée dans la page. Une dimension animée (largeur, hauteur) se déclare. 🔒 `npm run lint:mouvement` (27/09/2026 : 64 transitions sur 74 écrivaient la leur) | `styles/socle.css` |
| corps déplié | **entre** en 200 ms (fondu + 4 px), **sort** sans délai ; jamais la hauteur animée. Le corps porte **`.carte-corps`** | `composants.css` (`.carte-liste .carte-corps`) |
| appui | `scale(0.97)` sur `:active`, `transform` seul ; pas sur une icône `aria-pressed` (déjà à 115 %) | `composants.css` (`.btn`, `.btn-icon*`, `.signaler-inline`) · `Pastille.svelte` |
| animation sans fin | réservée à une ATTENTE (spinner, squelette, assistant qui travaille) — jamais décorative : ce qu'on voit plusieurs fois par jour ne s'anime pas. 🔒 `npm run lint:animations-infinies` (exceptions déclarées) | `composants.css` (`spin`) · `BadgeNouveau` (fixe) |
| modale | entre depuis le CENTRE : fondu + 96 % → 100 %, 200 ms `--ease-out` (`modale-entree`), fondu seul si le mouvement est réduit | `.modal`, `.modal-box` |
| message | **deux régimes** (arbitré le 26/09/2026, `emil-design-eng`) : un message SIMPLE — enregistré, erreur — va au coin fixe (`Toast` : bas à droite, bas au centre sous 767 px), une place prévisible ; il repart par où il est venu, se ferme par son ×, et une **erreur reste jusqu'à ce qu'on la ferme** (trois au plus, sans doublon) — la réussite part seule, retenue au survol, au focus et onglet caché ; chaque toast porte son rôle — `alert` pour une erreur, `status` sinon —, jamais une région qui RECOPIE son texte (lu deux fois) (#2168, 🔒 `e2e/toast.spec.ts`) ; la SUITE d'un geste sur un élément naît de l'élément — bulle ancrée, origine au déclencheur, 200 ms `--ease-out`, fermée au clic dehors, à Échap, au défilement | `Toast.svelte` · `BoutonLien` (« Lien copié · L'envoyer par courriel ») |
| explication | une phrase qui s'ouvre AU TOUCHER, au clic et au clavier, jamais un `title` seul (au doigt il ne se montre pas) : `Infobulle` — vrai bouton, nom accessible, fermée au clic dehors, à Échap (le focus revient), au défilement ; elle se retourne au bord de l'écran. Un point mesuré conforme / à corriger / inconnu se rend par `CocheConformite` : trois FORMES (✓ ✗ ?), jamais ✓ pour une mesure absente, et la phrase dit le fait selon l'état (15/10/2026) | `Infobulle.svelte` · `PastilleLecture` · `CocheConformite` |
| survol | ce qui ne sert qu'à la souris passe sous `@media (hover: hover) and (pointer: fine)` — au doigt, `:hover` reste collé. 🔒 `npm run lint:survol` (26/09/2026) : les feuilles communes sont rangées, les composants sous **plafond décroissant** | `normes.css` (`.carte-liste`, `.ec-titre`) · `.attenue` des cartes · toute `src/styles/` |
| transitions | les propriétés **nommées**, jamais `all` | partout |
| mouvement réduit | coupe les glissements ; garde le fondu et l'appui (3 % sur place = retour d'état) | `composants.css` · accueil (`tableau-de-bord`, `RaccourcisRapides`) |

⚠️ **Une carte neuve** : son corps déplié porte `class="carte-corps …"`, sinon il
apparaît sec, sans que rien ne le signale. Les quatre cartes à corps de lecture
le portent (affaire, actualité, annonce, membre) ; contrat et prestataire n'ont
qu'un formulaire d'édition, qui n'entre pas.

🔴 **Le chevron d'en-tête s'appelle `.chevron-carte`**, et c'est lui seul que
`.carte-liste.expanded` fait tourner. La règle visait `.chevron` : TOUT chevron
d'une carte dépliée — « Gérer les photos », une section repliée dans le corps
d'une affaire — paraissait ouvert avant tout clic. Trouvé en mesurant l'essai
dans un navigateur, pas en le relisant.

## 18. LA CHARTE — tailles de texte et couleurs d'état (arbitré le 27/09/2026, #1055)

Arbitré sur maquette, et posé par l'utilisateur comme règle **de tout le
projet** : https://claude.ai/artifact/5EUqnbiH4HSF8wJe4khAgP

| Quoi | Règle | Où elle se lit |
|---|---|---|
| valeur qui A un jeton | elle s'écrit **par le jeton** (`#fff` → `var(--color-surface)`, `0.8rem` → `var(--fs-sm)`) — sans plafond : 85 étaient revenues entre le 27/09 et le 10/10/2026 (#1571) | `egalesAUnJeton`, qui lit les jetons dans `styles/socle.css` |
| repli sur un jeton défini | `var(--color-border, #e5e7eb)` : le jeton existe, le repli est **mort** — on écrit `var(--color-border)` (#1571, 21/10/2026). Une variable que RIEN ne définit (`--color-bg-alt`, `--color-bg-subtle`…) n'est pas un jeton : seul son repli s'applique, c'est une valeur en dur déguisée — un fond neutre s'écrit `var(--color-neutre-fond)`. Sans repli, la propriété est perdue sans un mot (la FAQ, la frise des contrats) | `repliMortsDe` (`scripts/lib-charte-jetons.mjs`) · `npm run lint:variables-css` (`scripts/check-variables-css.mjs`) : toute `var(--nom)` est définie quelque part — sans plafond |
| taille de texte | un jeton `--fs-*` ; une valeur hors échelle se range au cran **supérieur** — aucun texte ne rétrécit. La RACINE, qui les décide tous, s'écrit en pourcentage : `100 %`, `87,5 %` sous 768 px ; un champ au téléphone prend `--fs-saisie-tactile` (16 px, n° 76) | `styles/socle.css` · la table de rangement dans `scripts/check-charte-valeurs.mjs` (`TAILLES_HORS_ECHELLE`) · 🔒 `npm run lint:taille-racine` |
| couleur d'état | `--color-danger`, `--color-success`, `--color-warning` ; un fond **se teinte depuis le jeton** (`-fond`), un filet clair aussi (`-bordure`) — jamais le rouge, le vert ou l'ambre de Tailwind | `styles/socle.css` · `COULEURS_ETAT_ETRANGERES` dans le même contrôle |
| texte d'avertissement | `--color-warning-texte` : `--color-warning` fait 3,62 sur blanc, il sert au cadre, à l'icône, à l'aplat — **jamais au texte** ; un pictogramme (étoile, puce) se déclare | `styles/socle.css` · 🔒 `npm run lint:texte-avertissement` (#2167 : quatre textes l'avaient pris, le jeton échappait au contrôle des valeurs) |
| texte clair sur un aplat (bouton, pastille retenue, compteur) | le texte : `--color-sur-plein` (`--color-sur-voile` sur un voile noir translucide) ; l'aplat : `--color-<état>-plein` (`primary`, `danger`, `success`, `accent`) — jamais `color: var(--color-surface)` ni `#fff`, jamais le jeton nu : au mode sombre (#2174) le texte d'un lien s'éclaircit et l'aplat reste foncé, deux valeurs | `styles/socle.css` · 🔒 `npm run lint:aplats` |
| texte sur l'OR (avatar, médaillon, pastille) | `--color-sur-accent` — le blanc n'y fait que 2,61:1 ; l'aplat, `--color-accent-plein` (#2174, S3) | `styles/socle.css` · 🔒 `npm run lint:aplats` |
| bordure d'un CHAMP de saisie | `--color-border-champ` (3:1, WCAG 1.4.11) ; `--color-border` est un filet décoratif, jamais le contour d'un champ (#2174, S3 — `.field` et l'éditeur riche ; les champs qu'un composant habille seul suivent en S4) | `styles/champs.css` |
| texte d'un badge | ≥ 4,5 sur son fond, **mesuré** par le contrôle pour chaque `.badge-*` ; sinon un dérivé `-texte` (`--color-success-texte`, #1410) | `styles/composants.css` |
| note par étoiles | proposition **B** : les étoiles portent la teinte d'état, le chiffre reste en couleur de texte ; en saisie, étoiles pleines en `--color-warning` | `NoteEtoiles.svelte` |
| badge d'état tiré d'une table | `<Badge teinte={TABLE[clé]}>` — teinte posée en `class:` ; `compact` pour le cran `--fs-2xs`. Une teinte écrite sans règle `.badge-*` se déclare avec son ticket dans `SANS_REGLE` (vide depuis #1986). Une teinte de catégorie neuve prend ses jetons dans `socle.css` (`--color-violet`, `--color-sarcelle`) ; `e2e/badges-roles` exige un fond de chaque rôle | 🔒 `npm run lint:badge` (#1571) |
| encart d'avertissement | `EncartAvertissement`, et lui seul — `compact` sous un champ, la marge chez l'appelant ; un fond d'avertissement ailleurs est un **emprunt de teinte** (survol, badge, carte mise en avant) et se déclare dans le contrôle, avec son nombre (#1455) | 🔒 `npm run lint:encart-avertissement` |

⚠️ **Les palettes de CATÉGORIES ne sont pas des états** et restent hors de la
règle : la teinte d'un type du fil (`#lib/flux`), d'un périmètre, d'une colonne
de kanban, d'une nature (`--nature-fort`), l'orange de l'urgence, `.badge-yellow`
(#495). Les confondre ferait perdre ce qui les distingue.

🔒 **Une teinte choisie par donnée se dit par son jeton, jamais par une valeur**
(#2174, lot S2 du mode sombre) : le type d'une rubrique du fil `var(--fil-rouge)`
(+ `-fond`), le rang d'un périmètre `var(--teinte-N)`, l'étape d'un kanban
`var(--kanban-ag)`, une tuile d'import `var(--color-import-lie)`. Le code porte
la chaîne `'var(--…)'`, `socle.css` la valeur — le bloc sombre redéfinit donc
chaque palette en un seul endroit. Une teinte neuve s'y ajoute, nommée par
l'usage, jamais en doublon d'un jeton existant (`annonce` prend `--color-orange`,
`publication` `--color-primary-light`). Un fond qui est la teinte à ~10 % ne
s'écrit pas `{couleur}1a` (suffixe hexadécimal, faux sur une variable) : le
composant pose `style="--kb-teinte:{couleur}"` et la feuille
`color-mix(in srgb, var(--kb-teinte) 10.2%, transparent)`. Le manifeste de
l'application installée, qui ne lit pas de variable CSS, est tenu à la valeur de
`--color-primary` / `--color-surface` par le même contrôle. 🔒 `npm run
lint:couleurs-ts`, `e2e/teintes-jetons.spec.ts` (la chaîne aboutit à une couleur
dans le navigateur), `api/tests/test_flux_apparence.py` (contraste mesuré sur la
valeur résolue).

🔒 **Le thème SOMBRE ne s'écrit que dans `styles/palette-sombre.css`** (#2174,
lot S3, palette arbitrée le 29/10/2026) : les jetons de `socle.css` y sont
redéfinis sous `:root[data-theme='dark']`, une fois — la copie « Auto » (système
en sombre) est générée au build par `scripts/vite-palette-sombre.mjs`. Un écran
ne porte ni `prefers-color-scheme` ni `data-theme` : il lit les jetons. Un jeton
de couleur neuf prend sa valeur sombre dans la palette, ou se déclare identique
avec sa raison (`IDENTIQUES`, `scripts/palette-sombre-paires.mjs`) ; un couple
texte/fond neuf s'ajoute à la table `PAIRES`, mesurée dans les deux thèmes.
🔒 `npm run lint:palette-sombre`, `e2e/palette-sombre.spec.ts` (forcé, Auto,
absent, impression). Personne ne voit le sombre avant la bascule (S5).
Les paires ne disent pas l'ÉCRAN : un composant qui lit le mauvais jeton passe la
table. Une zone parcourue au sombre (lot S4) se tient par un spec `@sombre` qui
relève l'écran RENDU — `releverContrastes` (`e2e/contraste-ecran.ts`) : chaque
texte sur son fond réel, chaque surface claire ; un dégradé est compté non mesuré.
La coque : `e2e/palette-sombre-coque.spec.ts`.

🔒 `npm run lint:charte-valeurs` refuse ces valeurs **sans plafond** — dans les
composants ET dans `src/styles/`, en style comme dans une chaîne JavaScript —
et donne le jeton de remplacement. Une couleur hexadécimale ne s'écrit plus
**nulle part** hors de `socle.css` (plafond à zéro, #2174 lot S1) : une teinte
neuve se range d'abord dans une famille existante (état, `info`, `violet`,
`sarcelle`, `orange`, `jaune` — un fond, un filet, un texte), et seulement à
défaut prend un jeton neuf nommé par l'usage, que le mode sombre redéfinira
(#2174 : 47 nuances écrites en dur, rangées sur 31 jetons dont 12 neufs). Les tailles
en dur restent sous leur plafond décroissant, qui compte les composants **et** les feuilles de
`src/styles/` hors `socle.css` (#1460) : remonter une valeur dans une feuille est
un déménagement, pas une dette soldée — le plafond ne bouge pas.

## Checklist UX (à vérifier avant commit)

**Une seule liste : `CLAUDE.md` → « Checklist avant commit » → Frontend.** Elle est
chargée à chaque session, celle-ci seulement quand on ouvre la skill. Les deux ont
coexisté et divergé : chacune avait des lignes que l'autre n'avait pas, et celle-ci
enseignait encore « périmètre pas affiché si `'résidence'` » quand le code n'en
contient plus un seul (claude-config#122, 23/09/2026).
