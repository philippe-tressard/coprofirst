# ux-patterns — La carte expansible (§3)

Annexe de `SKILL.md`, chargée à la demande (#2910) : la règle d'uniformisation, le
registre des arbitrages, le sommaire et la checklist avant commit sont dans `SKILL.md`.
Les numéros de § sont ceux de toujours : un renvoi « §N » se lit au sommaire.

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
| `EcheanceGouttiere` | la vignette d'ÉCHÉANCE d'une affaire datée, sous le classement : le délai SERVI (« J-8 », `meta.affaire.echeance`), puis la ou les dates (`fmtJourCourt`) ; rien pour une affaire sans date, la date seule si elle est close (arbitrage n° 81) | le créneau `gouttiere` de la carte du fil (`FluxCard`) ; 🔒 `e2e/echeance-gouttiere-fil` |
| `#lib/gouttiere` | le type `ClasseGouttiere` et `classeDe(table, marques, val)` : une notion déclare la **marque** de chaque valeur (`[icone, abrege]`), le libellé vient de sa table — `#lib/prestataires-gouttiere`, `classementAnnonce` | tout écran qui classe |
| `gouttiereAffaire(t)` | la gouttière d'une affaire, `{ quand, classe }` : `mis_a_jour_le ?? cree_le` et la nature (`natureDe`), à étaler sur `CarteListe` ; la teinte vient de `[data-nature]` (`--nature-fort`), sans elle le Bleu Seine | `CarteTicket`, `CarteActualite` (`#lib/tickets`) |
| `ReglagesListe` | la grille des réglages : libellés dans une colonne de la largeur de la gouttière, `ChampRecherche` **en tête**, puis `ChoixPastilles libelleDevant` / `FiltrePerimetre libelleDevant`, chacun avec `compte` | `FiltresAffaires` et toute page à réglages |
| `EnteteCarte` | la densité **aérée** est la base (l'ex-variante `ample`) : titre `--fs-lg`, aperçu `--fs-md` interligne 1,5, actions 26 px au bureau, 32 au doigt | toutes les cartes |
| `.carte-liste` | le filet sur trois côtés et 0,85 rem entre deux cartes (0,6 au téléphone) | `normes.css` |
| `IconeAction` | le pictogramme **au trait**, partout : gris `--color-text-muted`, Bleu Seine au survol ; plus de contexte de liste, plus d'émoji | tout bouton d'action icône ; 🔒 `npm run lint:actions-au-trait` |
| `IconeIA` | le geste qui lance l’assistant : ✨ au repos, ⏳ Bleu Seine qui clignote pendant l’appel — le bouton porte `aria-busy` (arbitrage n° 21) | tout bouton qui appelle l’IA ; 🔒 `npm run lint:geste-ia` |
| `.badge` | une **capsule** (coins de 6 px) sur tout le site ; `.badge-gray` neutre (pierre) sur la dernière ligne d'une carte (`.ec-tags`, `.pa`) | `composants.css` |

🔴 **Une carte archivée a UNE allure** (10/10/2026, `CarteListe archive`) : atténuée, pleine une fois dépliée et au survol (au pointeur seulement). Elle s'atténue par son FOND — l'encart neutre, à plat, sans ombre —, jamais par l'opacité : à 0,8, chacun de ses textes perdait l'AA (3,6:1 pour un badge, #2296). Il y en avait cinq — `.attenue` sous trois variantes, `.item-inactive` de la FAQ (0,55, jamais pleine), `.history-item` de l'affaire (liseré gris, sans le filet de la carte). Une classe passée par `class` vit dans `CarteListe` : le `<style>` de l'appelant ne l'atteint qu'en `:global(…)` — les teintes (`[data-nature]`, `[data-type-annonce]`) et les états vivent donc dans `normes.css`.

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
  `cible_visible` — le périmètre restreint **toujours**, d'où le cadenas —, résumée au
  serveur (`utils/lecture_pastille`) et tenue par les cas `objet` de `lecture_pastille.json`.
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

Le conteneur ne s'écrit que dans `CarteListe.svelte` (🔒 `npm run lint:carte-liste`) ;
un écran le POSE :

```svelte
<CarteListe id="ticket-{ticket.id}" {expanded} urgent={ticket.urgente} {archive}
  onDeplier={() => gestes.basculer(ticket)}>…</CarteListe>
```

La carte de l'écran ne garde chez elle que ses **différences**. Ne jamais y
redéfinir marge, bordure gauche, rayon, fond ou ombre.

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
