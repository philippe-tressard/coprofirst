# ux-patterns — Champs de formulaire (§9 à §9 quater bis)

Annexe de `SKILL.md`, chargée à la demande (#2910) : la règle d'uniformisation, le
registre des arbitrages, le sommaire et la checklist avant commit sont dans `SKILL.md`.
Les numéros de § sont ceux de toujours : un renvoi « §N » se lit au sommaire.

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
<label class="field">Titre <EtoileRequis vide={!titre} /><input type="text" bind:value={titre} /></label>

<div class="field">
  <label for="ah-source">Pré-remplir depuis une actualité</label>
  <select id="ah-source" bind:value={source}>…</select>
</div>
```

**Le champ ne porte aucune classe** : `.field input`, `.field select` et
`.field textarea` le gouvernent. Deux modificateurs nommés, et rien d’autre :
`champ-large` (§9 bis) et **`champ-en-ligne`**, pour un champ posé dans une
rangée où le `gap` du parent porte déjà l’espacement. Il y donne aussi la **même
hauteur** à une liste déroulante et à un champ de saisie voisins (plancher en `em`,
10/11/2026 : sans lui, le navigateur leur en donne deux, et leurs libellés se
décalent — 🔒 `e2e/champs-en-ligne-hauteur.spec.ts`). ⚠️ **Sous Safari, un
`<select>` natif ignore `min-height` et `padding`** (22 px contre 37) : la liste de la
rangée passe en `appearance: none`, flèche dessinée par les jetons — mesuré en WebKit
à la main, la CI ne joue que Chromium (2ᵉ signalement, même jour).

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

### 9 quater bis. Un badge qui se déplie le dit

Un badge est lu comme une **étiquette** : s'il est le bouton qui déplie un détail, il
porte le chevron `.chevron` **dans** le badge (▸ fermé, ▾ ouvert), la main au survol
et l'appui à 97 %. Sans lui, les gestes repliés derrière — corriger, retirer — sont
introuvables (#2745, l'avis d'un prestataire). Le motif vit dans
`NotationsPrestataire.svelte` (`.not-etat-bouton`) ; 🔒 `e2e/recap-avis-exercice.spec.ts`.
