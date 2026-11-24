# ux-patterns — Le cadre d'une entité, l'objet Documents, la liste au-dessus du formulaire (§0 à §0 ter)

Annexe de `SKILL.md`, chargée à la demande (#2910) : la règle d'uniformisation, le
registre des arbitrages, le sommaire et la checklist avant commit sont dans `SKILL.md`.
Les numéros de § sont ceux de toujours : un renvoi « §N » se lit au sommaire.

## 0. LE CADRE — une entité, quatre rendus (décidé le 17/08/2026)

**C'est la règle qui gouverne toutes les suivantes.** Les sections §9, §10, §13 et
§14 de cette skill en sont les instanciations ; en cas de désaccord, le cadre tranche.

> 📐 **Le cadre et sa maquette** : https://claude.ai/code/artifact/ed8e5dd8-67f0-4fd3-a0bc-e80653bac686
> 📊 **Le relevé des 42 couples menu/entité qui le fonde** : https://claude.ai/code/artifact/88087a21-8fe3-4463-8a35-a39f3032e5f3
> 🧠 **Le pourquoi** : le relevé ci-dessus, et les tickets 🎫 **#430**, lots #431 → #433
> → #432 (la fiche de mémoire qui le portait a été réduite le 12/11/2026 et renvoie ici).

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

**Sur l'affaire, aucune exception** (registre n° 84) : les deux arbitrées le
20/09/2026 — Au nom de pliée, Pièces jointes dépliée — ont été défaites les 21 et
22/09/2026, à l'écran (« pour éviter toute exception »). Les exceptions en vigueur se
lisent là où elles se déclarent, chacune avec sa raison, jamais recopiées ici :
`git grep -n exceptionPliage -- front/src/lib/entites`.

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

> Le cadre y est **résumé, pas recopié** — le détail vit dans l'artefact. La skill est
> découpée en annexes depuis le 23/11/2026 (#2910) : `SKILL.md` en donne le sommaire.

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
