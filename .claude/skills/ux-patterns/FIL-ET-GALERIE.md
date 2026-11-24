# ux-patterns — Fil d'évolutions, galerie de photos, visibilité du Kanban (§10 à §12)

Annexe de `SKILL.md`, chargée à la demande (#2910) : la règle d'uniformisation, le
registre des arbitrages, le sommaire et la checklist avant commit sont dans `SKILL.md`.
Les numéros de § sont ceux de toujours : un renvoi « §N » se lit au sommaire.

## 10. Fil d'évolutions

Structure pour les tickets/publications avec historique :

- `.evol-list` : border autour, séparateurs `<hr class="evol-sep">`
- `.evol-item` : `.evol-icon` + `.evol-body` (`.evol-meta` + `.evol-text`)
- Pagination : si > 7 → afficher 5 + bouton `.evol-more`
- Formulaire inline : pills type + textarea + select statut → `.evol-form`

### 10 bis. Le workflow d'un objet : UNE liste, et UN geste par écran

**Les états proposables ne s'écrivent jamais dans un écran.** Pour un ticket, ils
viennent de `#lib/tickets` (`STATUT_TICKET_OPTIONS`, `…_LABELS`, `…_BADGE`,
`STATUTS_TICKET_ACTIFS`, `estTicketActif`), qui répond à
`StatutTicket` côté serveur. `api/tests/test_statuts_tickets.py` échoue sur toute
liste réécrite — y compris dans un fichier qui importe déjà le module.
« Cette affaire est close » ne se calcule pas à l'écran : elle est SERVIE (`close`
de l'affaire, de la ligne du fil et des affaires liées ; `statuts[].clos` du
référentiel pour un état choisi), comme le libellé d'une catégorie
(`categorie_libelle`, #2511, `npm run lint:regles-partagees`).

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

- **la légende des bâtiments est DANS l'en-tête**, entre le titre et le lien
  (variante B parmi cinq, arbitrée à l'écran le 16/11/2026) : `LegendeBatiments`,
  pastilles rondes de `.graphique-legende`, libellé SERVI (`batiment_libelle` de
  `GET /perimetres`, « Bât. 1 (D) » — la lettre de l'acte ne vit qu'en base), couleur
  par `couleurPerimetre` comme les briques. Au téléphone elle passe sous le titre.
  🔒 `e2e/legende-batiments-kanban.spec.ts`.

La grille est donc en **flex** et non en `grid` : une grille donne la même part
à toutes ses colonnes, et c'est exactement ce qu'on ne veut plus.

⚠️ La bande verticale suit la hauteur de la plus haute colonne **par le flex**,
jamais par `height: 100%` sur son en-tête : un pourcentage résolu contre un
parent lui-même étiré tourne en rond, et le navigateur retombe sur la hauteur
de la fenêtre — mesuré, 622 px de colonnes pour 250 px de contenu.
