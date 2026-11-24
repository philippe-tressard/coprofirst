# ux-patterns — Droits, workflow et archivage, mouvement, charte (§15 à §18)

Annexe de `SKILL.md`, chargée à la demande (#2910) : la règle d'uniformisation, le
registre des arbitrages, le sommaire et la checklist avant commit sont dans `SKILL.md`.
Les numéros de § sont ceux de toujours : un renvoi « §N » se lit au sommaire.

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

| Ce qu'on demande | Où le lire |
|---|---|
| le nom que l'écran **affiche** | le champ servi `nom_proprietaire` (#2508), jamais recomposé |
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
| taille de texte | un jeton `--fs-*`, choisi par ce que l'élément EST : le TEXTE (`3xs` micro → `2xl`), un TITRE (`titre` pour un intertitre de contenu, `titre-page` pour le h1 d'une page), un PICTOGRAMME posé seul (`picto-sm`, `picto`, `picto-lg`, `picto-xl`), un CHIFFRE en vedette (`chiffre`, `chiffre-grand` pour une rangée de KPI) — n° 78 ; une valeur hors échelle se range au cran **supérieur** — aucun texte ne rétrécit. La RACINE, qui les décide tous, s'écrit en pourcentage : `100 %`, `87,5 %` sous 768 px ; un champ au téléphone prend `--fs-saisie-tactile` (16 px, n° 76) | `styles/socle.css` · la table de rangement dans `scripts/check-charte-valeurs.mjs` (`TAILLES_HORS_ECHELLE`) · 🔒 `npm run lint:taille-racine` |
| couleur d'état | `--color-danger`, `--color-success`, `--color-warning` ; un fond **se teinte depuis le jeton** (`-fond`), un filet clair aussi (`-bordure`) — jamais le rouge, le vert ou l'ambre de Tailwind | `styles/socle.css` · `COULEURS_ETAT_ETRANGERES` dans le même contrôle |
| texte d'avertissement | `--color-warning-texte` : `--color-warning` fait 3,62 sur blanc, il sert au cadre, à l'icône, à l'aplat — **jamais au texte** ; un pictogramme (étoile, puce) se déclare | `styles/socle.css` · 🔒 `npm run lint:texte-avertissement` (#2167 : quatre textes l'avaient pris, le jeton échappait au contrôle des valeurs) |
| texte ou trait clair sur un aplat (bouton, pastille retenue, compteur, initiales d'un avatar, pointillés, quart d'un indicateur) | le texte et le trait : `--color-sur-plein` (`--color-sur-voile` sur un voile noir translucide) ; l'aplat : `--color-<état>-plein` (`primary`, `danger`, `success`, `accent`) — jamais `var(--color-surface)` ni `#fff` en `color`, `border*`, `outline*`, `stroke`, `fill` ou `--avatar-color`, jamais le jeton nu : au mode sombre (#2174) la surface devient sombre, et ce qu'on posait dessus en blanc avec elle (S4b : trois traits passaient sombre sur sombre) | `styles/socle.css` · 🔒 `npm run lint:aplats` |
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
absent, impression). **Qui le voit** (S5, 30/10/2026) : tout appareil réglé en
sombre — Automatique est le défaut —, ou qui a choisi Sombre dans le Profil. Le
choix est un cookie d'appareil, lu par le serveur qui pose l'attribut et les balises
`color-scheme` / `theme-color` ; il ne se décide qu'à `#lib/theme.ts`, et le seul
sélecteur est `ChoixTheme` (Profil). 🔒 `e2e/bascule-theme.spec.ts`.
Les paires ne disent pas l'ÉCRAN : un composant qui lit le mauvais jeton passe la
table. Une zone parcourue au sombre (lot S4) se tient par un spec `@sombre` qui
relève l'écran RENDU — `releverContrastes` (`e2e/contraste-ecran.ts`) : chaque
texte sur son fond réel, chaque surface claire ; un dégradé est compté non mesuré.
La coque : `e2e/palette-sombre-coque.spec.ts`.
Le CLAIR se relève de même (#2296) : la zone des listes et du kanban, le Reporting et la
télémétrie ont leur passe `@clair`, sans écart déclaré. Un texte ne s'atténue jamais par
`opacity` (il y perd l'AA) : une colonne vide, une carte archivée se disent autrement.

🔒 **Un aperçu de support imprimé ou envoyé reste CLAIR** (#2174, S4d) : l'affiche
du hall, le courriel de la Diffusion, le corps d'un modèle de courriel se
regardent pour valider ce qui sortira — papier et messagerie ne suivent pas le
thème. L'élément porte `class="ilot-clair"` : il partage la règle `:root` de
`socle.css` (les jetons clairs, sans recopie) et `styles/ilots-clairs.css` lui
donne `color-scheme: light` et le fond blanc. Tout `<iframe>`, et chaque support
rendu sans cadre (déclaré dans `SUPPORTS`), la porte — 🔒 `npm run
lint:ilots-clairs`, `e2e/sombre-zone-d.spec.ts`. Une image téléversée composée
pour le clair (le logo) prend un fond par jeton, invisible au clair
(`--color-fond-logo`), jamais un filtre ni une seconde image.

🔒 `npm run lint:charte-valeurs` refuse ces valeurs **sans plafond** — dans les
composants ET dans `src/styles/`, en style comme dans une chaîne JavaScript —
et donne le jeton de remplacement. Une couleur hexadécimale ne s'écrit plus
**nulle part** hors de `socle.css` (plafond à zéro, #2174 lot S1) : une teinte
neuve se range d'abord dans une famille existante (état, `info`, `violet`,
`sarcelle`, `orange`, `jaune` — un fond, un filet, un texte), et seulement à
défaut prend un jeton neuf nommé par l'usage, que le mode sombre redéfinira
(#2174 : 47 nuances écrites en dur, rangées sur 31 jetons dont 12 neufs). Les tailles
sont à **zéro** elles aussi depuis #2313 (30/10/2026, arbitrage n° 78) : un `font-size`
en `rem` ne s'écrit plus nulle part hors de `socle.css`, composants **et** feuilles de
`src/styles/` (#1460). Une taille neuve prend le cran de ce que l'élément EST.
