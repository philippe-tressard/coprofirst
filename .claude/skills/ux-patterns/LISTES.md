# ux-patterns — Onglets, pastilles, recherche, aperçu, archivage (§4 à §8)

Annexe de `SKILL.md`, chargée à la demande (#2910) : la règle d'uniformisation, le
registre des arbitrages, le sommaire et la checklist avant commit sont dans `SKILL.md`.
Les numéros de § sont ceux de toujours : un renvoi « §N » se lit au sommaire.

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

### Le champ lui-même — UN objet sur tout le site (#2308, 29/10/2026)

Demandé : « standardisée sur tous les champs de saisie RECHERCHE ; l'objet doit
être standard », puis « le champ est de la même couleur que le fond ». Cinq
maquettes, la **B** retenue :

- `ChampRecherche`, et lui seul : libellé « Recherche » devant, saisie **blanche**
  (`--color-surface`) avec la loupe, la croix « Effacer la saisie » dès qu'il y a
  du texte, et dessous l'aide composée par le composant à partir de `dans`
  (obligatoire) : « Cherche dans : … — sans tenir compte des accents ni des
  majuscules. »
- L'aide ne promet que le vrai : une liste reçue filtre par `contientTousLesMots`
  (`#lib/texte`) ; une recherche au serveur qui garde les accents passe
  `sansAccents={false}` (le compte d'un locataire).
- Un bouton (« Chercher ») se pose dans le slot ; `on:keydown` est relayé.
- Exception déclarée : `ChoixAffaire`, un sélecteur dont le libellé nomme ce
  qu'on choisit. 🔒 `npm run lint:recherche`.

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
