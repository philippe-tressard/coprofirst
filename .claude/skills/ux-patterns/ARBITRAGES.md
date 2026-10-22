# Registre des arbitrages d'interface — 5Hostachy

Ce qui a été **tranché**, quand, sur quel ticket, **pourquoi**, et ce qui a été
**écarté**. La règle se développe dans `SKILL.md` (le « § » de chaque entrée) ; ce
registre ne dit que la décision, sa provenance et ce qu'elle interdit de refaire.
📖 `standards/12-documentation.md` §4 (le pourquoi, daté) et §5 (journal de décisions).

**Quand l'ouvrir : avant toute modification d'écran, de composant ou de libellé**
(étape 1 de la règle d'uniformisation de `SKILL.md`). La liste, puis la notion :

```bash
grep -n "^### n° [0-9]" .claude/skills/ux-patterns/ARBITRAGES.md
grep -n -i "<notion>" .claude/skills/ux-patterns/ARBITRAGES.md
```

## Quand une demande défait une entrée

1. **Le dire avant d'agir** : le numéro, la date, le pourquoi. Une demande peut défaire
   un arbitrage — encore faut-il que ce soit su.
2. Si l'utilisateur maintient : **nouvelle entrée** (numéro suivant), l'ancienne passe
   `remplacé par n° X`. **Jamais d'effacement** : elle dit ce qu'on a déjà essayé.
3. Un arbitrage se rend **par l'utilisateur** ; une règle que j'ai dérivée seule se note
   « non dit » ou « règle dérivée », et se rediscute plus librement (`standards/01` §1).

## Le format

```
### n° N · <statut> — <la décision, en titre court>
<date> · <ticket> · <par> · <§ de SKILL.md>
- **Décidé** : ce qui vaut aujourd'hui.
- **Pourquoi** : le constat ou la citation qui l'a fait naître.
- **Écarté** : ce qui a été essayé ou proposé, et refusé (si quelque chose l'a été).
- **Tenu par** : le contrôle qui le fait respecter — ou « aucun garde-fou nommé ».
- **Historique** : les révisions datées (s'il y en a).
```

| Statut | Sens |
|---|---|
| `en vigueur` · `révisé` | s'applique ; pour `révisé`, l'Historique dit ce qui a changé |
| `remplacé par n° X` | **historique** : ne plus l'appliquer, lire le n° X |
| `à arbitrer` | deux entrées, ou la skill et le code, divergent : question pour l'utilisateur |
| `ouvert` | question posée, **non tranchée** — ce n'est PAS une décision |

**Ticket** : `#N` (issue ou PR), `sans ticket` + version, ou `non retrouvé` — jamais un
numéro supposé. **Aucun nom de personne** (dépôt public) : « l'utilisateur ».
**Les n° 1 à 21** sont ceux de l'ancien tableau « Ce qui est tranché » de `SKILL.md`,
cités ailleurs (« arbitrage n° 21 », `CLAUDE.md`). Un numéro ne se réutilise jamais.

🔒 **Garde-fou : `npm run lint:arbitrages`** (`front/scripts/check-arbitrages.mjs`, en CI). Il refuse un titre hors forme,
un statut inconnu, un numéro sauté ou répété, une entrée sans provenance, « Décidé », « Pourquoi » ou « Tenu par »
(sauf `ouvert` et `remplacé`), un `remplacé par n° X` vers une entrée absente, tout « arbitrage n° N » cité dans le dépôt
vers un numéro absent, et un `lint:*` ou un fichier de test de « Tenu par » qui n'existe pas. `--selftest` prouve chaque refus.

---

### n° 1 · en vigueur — Le geste de dépliage est asymétrique
18/08/2026 · non retrouvé · l'utilisateur, à l'écran · §3 « Le geste de dépliage »
- **Décidé** : carte repliée, clic n'importe où ; carte dépliée, **seul le titre** replie.
- **Pourquoi** : « cliquable sur toute la zone pour déplier » puis « clic sur le titre seul pour le repliement — pour permettre de sélectionner le texte ».
- **Écarté** : « le titre et lui seul », puis « toute la carte » — trois allers-retours ; l'objection « la carte entière intercepte la sélection » était juste mais hors sujet (le corps déplié arrête déjà la propagation).
- **Tenu par** : `CarteListe` (`onDeplier`), `npm run lint:carte-liste`.

### n° 2 · en vigueur — Le survol colore le TITRE, jamais le fond
17-18/08/2026 · non retrouvé · l'utilisateur, à l'écran · §3
- **Décidé** : au survol d'une carte repliée, le titre passe en couleur primaire, sans soulignement ; le fond ne change pas.
- **Pourquoi** : le fil d'activité fait référence pour le survol comme pour le geste.
- **Écarté** : le fond qui change au survol.
- **Tenu par** : `normes.css` (`.carte-liste:not(.expanded):has(.ec-titre-btn):hover .ec-titre`), sous `@media (hover: hover)`. ⚠️ Le §3 « Le geste de dépliage » écrit encore « le fond change au survol » : périmé (vérifié dans le code le 18/10/2026).

### n° 3 · en vigueur — Le liseré gauche bleu est la référence
17-18/08/2026 · non retrouvé · l'utilisateur, à l'écran · §3
- **Décidé** : le liseré gauche de `.carte-liste` qui passe au bleu ; sauf au fil, où il porte la couleur du type.
- **Pourquoi** : non écrit.
- **Tenu par** : `.carte-liste` (une seule définition, `normes.css`).

### n° 4 · révisé — L'en-tête de carte : le titre a sa ligne
18/08/2026 · non retrouvé · l'utilisateur, à l'écran · §3 « La structure d'en-tête »
- **Décidé** : titre en gras avec actions et chevron sur la 1ʳᵉ ligne · aperçu sur trois lignes · pastilles en dernière ligne. La date est dans la gouttière (n° 19).
- **Pourquoi** : sur téléphone, le titre partageait sa ligne avec les tags et se réduisait à trois points.
- **Écarté** : titre, tags, date et icônes sur une seule ligne.
- **Tenu par** : `EnteteCarte`, `npm run lint:entete-carte`, `e2e/ligne-pastilles.spec.ts`.
- **Historique** : 18/09 — ordre dicté à l'écran (actions sur la ligne du titre, pastilles en dernier) ; 27/09 — au téléphone la dernière ligne passe à la ligne (l'auteur s'y lisait tronqué) ; 10/10 — « date à droite » cède à la gouttière (n° 19).

### n° 5 · révisé — L'ordre des actions : 🔗 d'abord, toutes dans l'en-tête
18/08/2026 · non retrouvé · l'utilisateur, à l'écran · §3
- **Décidé** : 🔗 copier le lien · 🔄 suite · ✏️ modifier · 📦 archiver, puis le chevron — dans l'en-tête, jamais dans le corps.
- **Pourquoi** : 🔗 est la seule action que tout le monde a : ailleurs, elle sauterait d'un cran selon les droits (05/09). Un crayon caché dans le corps déplié rendait la suppression plus accessible que la correction (10/09).
- **Écarté** : un ordre inversé sur les actualités ; une action dans le corps.
- **Tenu par** : `IconeAction`, `CarteModifiable`, `npm run lint:actions-au-trait`.
- **Historique** : 05/09 — 🔗 en tête ; 24/09 et 02/10 — 📦 remplace 🗑️ sur la vue principale (n° 9) ; 10/10 — pictogrammes au trait, plus d'émoji (n° 19).

### n° 6 · en vigueur — Le mode se lit sur l'icône qui l'a ouvert
18/08/2026 (soir) · non retrouvé · l'utilisateur, à l'écran · §13 bis
- **Décidé** : dans la carte d'un objet, l'icône qui a ouvert le formulaire s'inverse (`aria-pressed`) ; un formulaire encadré de création garde son titre.
- **Pourquoi** : « les titres d'état je ne trouve pas ça beau : je mettrais l'icône concernée en plus gros ou inversée ».
- **Écarté** : un titre d'état au-dessus du formulaire (posé le matin même) ; un simple changement de teinte, indistinct du survol.
- **Tenu par** : `styles/composants.css` (une seule règle) — aucun contrôle dédié.

### n° 7 · en vigueur — La section 1 ne porte QUE le titre
18/08/2026 · non retrouvé · l'utilisateur, à l'écran · §0
- **Décidé** : ce qui qualifie l'objet (catégorie, « Saisi pour ») est en section 2.
- **Pourquoi** : sur les tickets, la catégorie était rendue avant le titre.
- **Tenu par** : `npm run lint:etats`, `lint:section-nommee`.

### n° 8 · en vigueur — Déclarer un workflow et le tracer sont deux décisions
18/08/2026 · non retrouvé · l'utilisateur, à l'écran · §16
- **Décidé** : une petite annonce a un workflow — En cours · Réservé · Vendu · Donné · Annulé — et aucun fil d'évolutions.
- **Pourquoi** : la question de la section est « où en est l'objet ? », pas « qui agit ? » ; un vendeur qui a réservé ou vendu a un cycle que ses voisins lisent.
- **Écarté** : « l'annonce n'a qu'un acteur, donc pas de workflow » (écrit le matin même) ; importer `RubriqueHistorique` par réflexe.
- **Tenu par** : la déclaration de l'entité (`$lib/entites/`), `lint:etats`.

### n° 9 · révisé — L'archivage se calcule ; le conseil peut aussi ranger d'un geste
18/08/2026 · #1538 (révision) · l'utilisateur · §8, §16
- **Décidé** : 30 jours après un état terminal, mesuré sur `statut_change_le`, calculé par le serveur (`archivee`). Sur une affaire ou une actualité, le conseil peut aussi archiver (📦) ; prestataires et contrats n'ont que ce geste, et ↩️ pour ressortir. La suppression ne s'offre qu'aux Archives.
- **Pourquoi** : `mis_a_jour_le` repousserait l'archivage à chaque faute corrigée ; un archivage recalculé par l'écran a déjà fait diverger liste et Historique (17/07).
- **Écarté** : un bouton d'archivage seul, sans calcul (deux notions pour la même chose) ; un 🗑️ intitulé « Archiver ».
- **Tenu par** : `utils/archivage.REGLES`, `api/tests/test_suppression_aux_archives.py`, `e2e/archives-prestataires`.
- **Historique** : 24/09 — « aucun bouton 📦 » révisé pour affaires et actualités (« c'est une suppression ou pas ? ») ; 02/10 — prestataires et contrats (#1538).

### n° 10 · en vigueur — Deux droits : éditer, commenter
18/08/2026 · non retrouvé · l'utilisateur · §15
- **Décidé** : éditer = auteur · « saisi pour » · admin ; commenter = les mêmes + le conseil syndical.
- **Pourquoi** : « Seul l'auteur peut l'éditer ou le commenter, avec l'admin, mais aussi le CS peut commenter, pas éditer ». Le résident « saisi pour » était le seul à ne pas pouvoir corriger ce qui parle de lui.
- **Tenu par** : `peut_editer` / `peut_commenter`, `test_droits_editer_commenter.py`, `npm run lint:droits`.

### n° 11 · en vigueur — L'écran dit ce que le serveur fait, ni plus ni moins
18/08/2026 · non retrouvé · règle dérivée · §15
- **Décidé** : un geste ne s'affiche que s'il est permis, et tout geste permis s'affiche.
- **Pourquoi** : plus large, un 403 sur un geste proposé ; plus étroit, une capacité introuvable — les deux le même jour dans `RubriqueHistorique`.
- **Tenu par** : `npm run lint:droits` (en partie).

### n° 12 · en vigueur — L'objet Documents a UNE forme
11/09/2026 · commits #911, #912 · l'utilisateur, à l'écran · §0 bis
- **Décidé** : pastilles « TYPE: nom » en rangée, puis le bouton et le champ de libellé sur la même ligne, puis le compteur.
- **Pourquoi** : trois formes selon l'écran (tickets, actualités, contrats) pour le même objet.
- **Écarté** : bouton et champ empilés ; le champ avant le bouton ; un intitulé au-dessus du champ.
- **Tenu par** : `PastilleFichier`, `FichiersUpload`, `npm run lint:fichiers`.

### n° 13 · en vigueur — La dernière ligne d'une carte est UNE
27/09/2026 · #1329, #1373 · l'utilisateur, à l'écran · §3 « La dernière ligne »
- **Décidé** : catégorie · état · 🔹 · qui la lit · ⚡ Urgente · marqueurs · #numéro · ✍️ auteur · ✨ ; le fil la rend à l'identique, sans 📌.
- **Pourquoi** : la carte d'actualité et le fil différaient de l'affaire sur neuf points.
- **Tenu par** : `PastillesAffaire`, `npm run lint:pastilles`, `e2e/ligne-pastilles.spec.ts`, `test_flux_pastilles.py`.

### n° 14 · en vigueur — L'urgence se dit ⚡, orange, partout
27/09/2026 · #1329 (v2.65.9) · l'utilisateur, à l'écran · §3 Règles
- **Décidé** : un seul glyphe, `GLYPHE_URGENCE` ; 🚨 est banni, manuel compris.
- **Pourquoi** : case, bouton, bandeau et manuel disaient 🚨, la carte ⚡.
- **Écarté** : 🚨.
- **Tenu par** : `npm run lint:pictogrammes`, `lint:options-en-double`.

### n° 15 · en vigueur — Un seul sélecteur de fichiers, 44 px au doigt
27/09/2026 · #1329 · l'utilisateur · §0 bis
- **Décidé** : `FichiersUpload` partout ; les gestes réellement différents se déclarent dans `SELECTEURS_NATIFS`.
- **Pourquoi** : un `<input type="file">` nu restait (`FormulaireDocument`) ; le bouton 📎 faisait 22 px.
- **Tenu par** : `npm run lint:fichiers`, `e2e/depot-fichier.spec.ts`.

### n° 16 · en vigueur — Le manuel montre la VRAIE pastille
27/09/2026 · #1329 (v2.66.2) · l'utilisateur · skill `user-manual`
- **Décidé** : la pastille du manuel est celle du site, phrase au survol recalculée.
- **Pourquoi** : non écrit ici — voir la skill `user-manual`.
- **Écarté** : une couleur propre au manuel.
- **Tenu par** : voir la skill `user-manual`.

### n° 17 · en vigueur — Un seul bloc déplié à la fois, partout
30/09/2026 · v2.87.0 (PR #1487) · l'utilisateur, demande · §3 Règles, `$lib/accordeon`
- **Décidé** : cartes, années d'archives, colonnes vides du kanban, sections de formulaire, réponses, `<details>` — « sans exception, formulaires compris ». Deux exceptions : une section **modifiée** reste ouverte, une carte **en correction** aussi. Une seule mécanique (`basculer`, `membre`, `listeMembre`, l'écouteur des `<details>` posé par le layout) ; le bloc ouvert remonte à l'écran quand le repli d'un voisin l'en a fait sortir (`amenerEnVue`).
- **Pourquoi** : signalé dans Admin › IA : « on se trouve à la fin de la section ouverte ».
- **Écarté** : un `Set` d'ouverture (« ce n'est pas un accordéon », colonnes vides du kanban).
- **Tenu par** : `npm run lint:accordeon`, `e2e/accordeon`.

### n° 18 · en vigueur — Le compteur d'une rangée de filtres : sur la pastille RETENUE seule
10/10/2026 · v2.130.0 (#1794), v2.131.0 · l'utilisateur, sur maquette · §5
- **Décidé** : la pastille retenue — « Tous » compris — porte le nombre affiché (filtres et recherche appliqués), en vignette `Compte` inversée ; les autres n'en portent pas.
- **Pourquoi** : « compteur uniquement pour la pastille retenue », à appliquer à toute nouvelle demande.
- **Écarté** : un nombre dans chaque pastille (maquette B, livrée en v2.130.0), puis quatre autres variantes — maquette J retenue parmi dix.
- **Tenu par** : `npm run lint:compte-filtres`, `e2e/compte-filtres-affaires`.

### n° 19 · en vigueur — La page Affaires est le standard des listes du site
10/10/2026 · #1819 · l'utilisateur, sur maquette puis demande · §3 « La carte d'AFFAIRE »
- **Décidé** : gouttière à gauche (la date, jour en grand, puis ce qui classe), densité aérée, actions au trait (`IconeAction`), dernière ligne en capsules dont seuls l'état, « qui la lit » et l'urgence sont teintés. Briques `CarteListe`, `Gouttiere`, `ReglagesListe`. Un tableau reste un tableau (actions au trait et capsules, pas de gouttière).
- **Pourquoi** : « plus premium et aérée, sans perdre aucune information » ; puis, le soir même : « elle doit devenir un standard pour les autres pages similaires ».
- **Écarté** : quatre autres maquettes (B « Gouttière » retenue parmi cinq) ; la règle R5 « une page à la fois » a cédé à la demande explicite.
- **Tenu par** : `npm run lint:carte-liste`, `lint:actions-au-trait`, `e2e/gouttiere-nature`.
- **Historique** : maquette https://claude.ai/artifact/TUunrVHAwxQGhHgUn9wrGW. Remplace n° 44 (F1) et la « date à droite » du n° 4.

### n° 20 · en vigueur — Une affaire DÉPLIÉE se lit en trois étapes
16/10/2026 · v2.169.0 (PR #2031) · l'utilisateur, sur maquette · §3
- **Décidé** : `RubriqueEtape` — un jalon sur un rail à gauche, un encart teinté (neutre · bleu · vert), pliable. « La demande » · « La suite · n entrées » (trois, puis « plus anciennes ») · « La synthèse » en dernier (texte, puis chiffres). Une seule dépliée à la fois, la demande d'abord ; pliée, une étape dit l'essentiel sur une ligne (`resume`). La Suite de synthèse quitte le fil (`entreesDuFil`) ; repliée, la carte porte « 🧾 Synthèse ». Une suite se supprime après confirmation.
- **Pourquoi** : la maquette A du 15/10 avait des intitulés de deux styles et des limites floues ; sans résumé, le pliage cacherait la conclusion.
- **Écarté** : la maquette A sur la carte ; huit autres maquettes (G retenue parmi dix, en deux tours).
- **Tenu par** : `e2e/carte-affaire-close`, `e2e/fil-rubriques-affaire` (parité avec le fil).
- **Historique** : 18/10 — étendu au fil, qui s'ouvre sur « La suite » (n° 66). 20/10 — livré au fil (v3.4.0, #2078) : le fil rend `CorpsCarteTicket`, `ouverteParDefaut="suite"` ; `e2e/fil-rubriques-affaire` tient la parité.

### n° 21 · en vigueur — Lancer l'assistant IA : ✨, puis ⏳ qui clignote
17/10/2026 · sans ticket — v2.176.0 (PR #2063) · l'utilisateur, demande · §3, briques
- **Décidé** : `IconeIA {enCours}` — `sparkles` au repos, `hourglass` Bleu Seine qui clignote pendant l'appel (immobile sous `prefers-reduced-motion`) ; le bouton porte `aria-busy` et se désactive, à **pleine opacité**. ✨ ne se dit que de l'IA. La marque « rédigé avec l'assistant » (`MarqueIA`) n'est pas un geste et ne clignote pas.
- **Pourquoi** : « standardise partout le principe […] est-il possible de le faire clignoter ? » ; à demi-teinte, l'attente se lisait comme un refus.
- **Écarté** : ✨ sur la « Présélection recommandée » des accès d'un bail (une règle, pas l'assistant).
- **Tenu par** : `npm run lint:geste-ia`, `e2e/assistant-ia`.

### n° 22 · ouvert — Unifier Libellé → Titre, Notes / Contenu → Description ?
16/08/2026 · non retrouvé · question posée, non tranchée · §9 quinquies
- **Décidé** : rien. Décision fonctionnelle (libellés lus par les résidents), pas un renommage de classe.

### n° 23 · en vigueur — Le cadre : une entité, quatre rendus
17/08/2026 · #430 (lots #431, #433, #432) · l'utilisateur · §0
- **Décidé** : Affichage · Création · Édition · Évolution ; sections dans l'ordre de `SECTIONS_ORDRE` ; toute divergence entre rendus se déclare avec son motif (R4) ; un enrichissement se propose sur UN écran, se constate, puis se généralise (R5).
- **Pourquoi** : relevé de 42 couples menu/entité — mémoire `project_cadre_quatre_rendus`.
- **Écarté** : « Commentaire » comme nom du quatrième état (trop étroit).
- **Tenu par** : `npm run lint:etats`, `lint:ordre-sections`.

### n° 24 · en vigueur — Le bouton de soumission dit « Enregistrer », partout
17/08/2026 · #396 · l'utilisateur · §9 quinquies bis
- **Décidé** : « Enregistrer » au repos, « Enregistrement… » pendant l'envoi, sur tous les formulaires de création. Hors champ : authentification, imports, mot de passe.
- **Pourquoi** : sept formulaires portaient six libellés.
- **Écarté** : « Publier » / « Enregistrer brouillon » selon la case (la Diffusion le dit déjà).
- **Tenu par** : `npm run lint:soumission`.

### n° 25 · en vigueur — L'en-tête de page a UNE marge, 1,5 rem
17/08/2026 · #372 · l'utilisateur · §13
- **Décidé** : la prop `marge` d'`EntetePage` est retirée ; aucune exception.
- **Pourquoi** : six écrans divergeaient, le titre sautait d'une page à l'autre ; « la valeur du plus grand nombre gagne ».
- **Écarté** : centraliser les six valeurs dans une prop (lisibles, mais pérennes).
- **Tenu par** : `npm run lint:entetes`.

### n° 26 · révisé — Une actualité n'a pas de workflow… mais un suivi optionnel
18/08/2026 · non retrouvé · l'utilisateur · §16
- **Décidé** : pas de workflow d'affaire sur une actualité ; son Publié / Brouillon est une décision de diffusion. Depuis le 10/10, un **suivi optionnel** à trois états — Ouvert · Résolu · Annulé (`ETATS_SUIVI_ACTUALITE`).
- **Pourquoi** : « En cours », « Résolu » faisaient ressembler une annonce à un dossier suivi (ré-arbitré le 18/08, après l'avoir ouvert la veille).
- **Écarté** : le workflow complet d'une affaire.
- **Tenu par** : la déclaration (`sansObjet`), `$lib/suivi-actualite`.
- **Historique** : 10/10 — suivi optionnel, v2.131.0 (#1807). ⚠️ Le §16 dit encore « c'est définitif » : périmé (vérifié dans le code le 18/10/2026).

### n° 27 · en vigueur — La Diffusion se rouvre à l'édition
18/08/2026 · non retrouvé · l'utilisateur · §0
- **Décidé** : la section Diffusion est présente en édition ; **seule la transition décoché → coché envoie**.
- **Pourquoi** : « le CS doit pouvoir décider d'envoyer au syndic un objet déjà saisi ».
- **Écarté** : rouvrir la case sans que le serveur la consomme (elle promettrait un envoi qui n'a pas lieu).
- **Tenu par** : le serveur (transition seule) — aucun contrôle nommé dans la skill.

### n° 28 · en vigueur — Le kanban du calendrier EST un workflow
18/08/2026 · non retrouvé · non dit · §9 sexies
- **Décidé** : la section s'appelle Workflow ; un changement de colonne est une transition tracée.
- **Pourquoi** : ses colonnes répondent à « où en est cet objet ? ».
- **Écarté** : un second champ d'état « Suivi Kanban » ; ranger le kanban dans la Diffusion.
- **Tenu par** : `KANBAN_COLS` (`$lib/kanban`), contrôle du kanban (job `test-scripts`).

### n° 29 · en vigueur — Une seule largeur de saisie
18/08/2026 · non retrouvé · l'utilisateur · §9
- **Décidé** : `--largeur-saisie` (100 % du conteneur), posée par le squelette, sur tous les formulaires ; jamais une largeur écrite dans une page. Les modales gardent la leur.
- **Pourquoi** : le cap à 720 px arrêtait la boîte de création avant les cartes de la liste.
- **Écarté** : 640 / 720 px selon l'écran ; la liste `ROUTES_LARGEUR_PLEINE` (retirée).
- **Tenu par** : aucun garde-fou nommé.

### n° 30 · en vigueur — Le fil d'évolutions montre les photos en grand
18/08/2026 · non retrouvé · l'utilisateur, à l'écran · §11
- **Décidé** : `PiecesJointes format='grand'` là où l'on a demandé à voir (fil déplié, Historique) ; `'vignette'` là où l'on survole.
- **Pourquoi** : sur un suivi de calendrier, les photos sont tout le contenu, réduites à des timbres-poste.
- **Écarté** : la vignette dans le fil d'évolutions.
- **Tenu par** : aucun garde-fou nommé.

### n° 31 · en vigueur — L'annulation vit à côté d'« Enregistrer »
18/08/2026 · #367 (révision) · non dit · §13
- **Décidé** : le bouton d'ouverture (`BoutonNouveau`) s'efface pendant la saisie ; l'annulation est au pied du formulaire, jamais en double dans l'en-tête. Jamais de modale pour créer.
- **Pourquoi** : trois paradigmes de création, un bouton excentré, deux commandes d'annulation (signalé trois fois).
- **Écarté** : la bascule « + … » ⇆ « ✕ Annuler » dans l'en-tête (#367, 15/08).
- **Tenu par** : `BoutonNouveau`, `npm run lint:formulaires`.
- **Historique** : ⚠️ le §14 « Les trois règles » (règle 1) et son exemple disent encore « ✕ Annuler » dans l'en-tête : périmé (vérifié dans `BoutonNouveau.svelte` le 18/10/2026).

### n° 32 · en vigueur — L'administration est UNE page
19/08/2026 · non retrouvé · l'utilisateur, à l'écran · §9
- **Décidé** : un écran d'administration est un onglet (`Onglet*.svelte`), jamais une route ; ce qui attend un geste de l'admin est l'onglet « À traiter » (n° 62).
- **Pourquoi** : « fiche copropriété et Périmètre sont des pages autonomes alors que les autres sont intégrées au menu Paramétrage : uniformise cela ».
- **Écarté** : un bouton « ← Retour » posé la veille.
- **Tenu par** : `npm run lint:routes`.

### n° 33 · en vigueur — L'anatomie d'un écran d'administration
19/08/2026 · non retrouvé · l'utilisateur, à l'écran · §9
- **Décidé** : `EntetePage` + retour, `config-section`, `SectionFormulaire`, `.form-actions`, `.modal-footer` ; champ beige sur carte blanche ; pas d'émoji dans un titre de section.
- **Pourquoi** : « l'écran WhatsApp n'est pas très beau, fais ressortir les sections, on s'y perd visuellement ».
- **Tenu par** : `npm run lint:champs`.

### n° 34 · révisé — Le seuil des listes courtes : 6
29/08/2026 · #491 · l'utilisateur · §0 « Le seuil des listes courtes »
- **Décidé** : une liste de 6 entrées ou moins qui fait choisir se rend en pastilles — filtres ET champs de formulaire ; au-delà, une liste à l'allure de pastille (`PastilleDeroulante`). Le tri est la seule exception déclarée.
- **Pourquoi** : sept pastilles réécrites à la main ; le seuil est écrit pour que la question ne se repose pas à chaque écran.
- **Écarté** : un `<select>` natif dans une barre de filtres ; convertir un vrai `radiogroup` (perte d'accessibilité).
- **Tenu par** : `npm run lint:seuil-listes`.
- **Historique** : 06/09 — l'utilisateur dit « ≤ 5 », même verdict sur tout le produit ; 24/09 — `PastilleDeroulante` au-delà du seuil ; 26/09 — champs de formulaire compris (#1329).

### n° 35 · en vigueur — L'onglet actif se voit : trois marques
30/08/2026 · non retrouvé · l'utilisateur, à l'écran · §4 bis
- **Décidé** : liseré bas, couleur primaire, graisse 600 — les trois ; un écran ne redéfinit jamais `.tabs button` en entier.
- **Pourquoi** : « on ne voit pas l'onglet actif ; ajoute ce design dans l'UX et applique-le à tous ».
- **Écarté** : une marque seule.
- **Tenu par** : `styles/ecrans.css` — aucun contrôle dédié.

### n° 36 · remplacé par n° 39 — La modale, format standard d'édition
30/08/2026 · non retrouvé · l'utilisateur, à l'écran · §14 bis
- **Décidé** : (historique) l'édition d'un objet s'ouvre en modale.
- **Pourquoi** : « une édition interrompt une lecture ; déplier un formulaire au milieu d'une liste déplace tout ce qui est en dessous ».
- **Historique** : 06/09 — tranché autrement (n° 39) ; le raisonnement n'a pas été réfuté.

### n° 37 · en vigueur — Le cadre se pose là où le geste est connu
30/08/2026 · non retrouvé · règle dérivée · §14
- **Décidé** : le composant de formulaire pose son cadre s'il reçoit le geste (`modeEdition`) ; sinon l'écran appelant. Le choix vit dans `CadreFormulaire`.
- **Pourquoi** : poser le cadre dans la page oblige à deux branches qui montent le même formulaire.
- **Tenu par** : `npm run lint:formulaires`.

### n° 38 · en vigueur — Un onglet est une adresse
05/09/2026 · non retrouvé · l'utilisateur, demande · §4
- **Décidé** : chaque onglet et sous-onglet a son URL (`BarreOnglets`, `$lib/pages.ts`, `reroute`) ; plate pour un contenu, imbriquée pour une vue. Admin reste sur `?onglet=`.
- **Pourquoi** : envoyer une petite annonce ne donnait à copier que l'adresse de la page voisine ; « sauf admin », demandé.
- **Écarté** : un segment de reste `[...vue]` (il déplace les écrans) ; se replier sur le premier onglet pour une adresse inconnue.
- **Tenu par** : `test_liens_front.py`, `npm run lint:onglets-reserves`.

### n° 39 · en vigueur — Créer et corriger emploient la même boîte dans la page
06/09/2026 · non retrouvé · l'utilisateur, à l'écran · §14 bis
- **Décidé** : un seul format pour les deux gestes ; les modales restent pour confirmer, accompagner un geste, téléverser, la visionneuse.
- **Pourquoi** : « la boîte d'édition n'est pas standard à l'UX, elle apparaît dans une fenêtre indépendante […] pas de spécifique ».
- **Écarté** : la modale d'édition (n° 36).
- **Tenu par** : `npm run lint:formulaires`, `lint:geste-edition` (règle E).

### n° 40 · en vigueur — La correction s'ouvre à la place du corps de la carte
10/09/2026 · #889 · l'utilisateur, à l'écran · §14 ter
- **Décidé** : l'en-tête reste (titre, tags, actions), seul le corps cède la place au formulaire (`encadre={false}`) ; sans `cle`, rien ne défile. Composant : `CarteModifiable`.
- **Pourquoi** : « l'affaire modifiée passe en premier ! prends exemple sur tickets ».
- **Écarté** : en bas de page, en haut de page, la carte entière remplacée — trois positions en une journée.
- **Tenu par** : `npm run lint:geste-edition` (règles B à E).

### n° 41 · en vigueur — Ce qui qualifie la liste reste au-dessus du formulaire
12/09/2026 · non retrouvé · l'utilisateur, à l'écran · §0 ter
- **Décidé** : sous le titre de page : avertissement ou bandeau · filtres · formulaire ouvert · liste.
- **Pourquoi** : l'avertissement sur les tickets d'urgence disparaissait au moment précis où l'on en crée un.
- **Tenu par** : `npm run lint:filtre-avant-formulaire`.

### n° 42 · en vigueur — Le nom affiché est celui du propriétaire
12/09/2026 · #1104 (21/09) · l'utilisateur · §15
- **Décidé** : un objet « Saisi pour » affiche `nomProprietaire` ; la case de copie dit `nomCopie` — deux questions.
- **Pourquoi** : un écran affichait le rédacteur (`auteur_nom`) à trois lignes de la bonne fonction.
- **Écarté** : `objet.auteur_nom` dans un écran.
- **Tenu par** : `npm run lint:nom-proprietaire`, `test_proprietaire_expose.py`.

### n° 43 · en vigueur — La saisie qui accompagne un geste reste une fenêtre
14/09/2026 · #931 · non dit · §14
- **Décidé** : un motif (signaler au conseil) passe par `Saisie.svelte`, la version ouverte de `Confirmation`.
- **Pourquoi** : le motif ne crée ni ne corrige aucun objet ; la règle la plus déployée (seize confirmations) l'emporte.
- **Écarté** : ouvrir le motif dans la rangée (un état d'ouverture par ligne, retiré à seize appels).
- **Tenu par** : aucun garde-fou nommé.

### n° 44 · remplacé par n° 19 — La densité « F1 »
18/09/2026 · non retrouvé · l'utilisateur, à l'écran · §3 « La densité »
- **Décidé** : (historique) carte de ticket de 206 à 110 px ; actions à 22 px au bureau.
- **Pourquoi** : six essais ; les 13 px de blanc venaient des boutons, pas des marges.
- **Écarté** : les actions sorties du flux (`position: absolute`).
- **Historique** : 10/10 — relâchée par la forme aérée (n° 19). Le principe reste : chaque bloc décide de son espacement.

### n° 45 · révisé — Le kanban condensé
18/09/2026 · #1161 · l'utilisateur, à l'écran · §12 bis
- **Décidé** : la brique est `ItemKanban` (celle de `/tickets/kanban`) ; une colonne vide se réduit à son titre vertical, « Aucune affaire » lisible dans le pli ; l'accueil borne ses colonnes à `MAX_CARTES_ACCUEIL`.
- **Pourquoi** : 30 px au lieu de 200 pour une étape vide, rendus aux colonnes pleines.
- **Écarté** : la variante K4 (icône en dernière ligne) ; une colonne vide qui disparaît.
- **Tenu par** : `npm run lint:plafond-liste`.
- **Historique** : 19/09 — « utilise le même UX des briques » ; 20/09 — le mot dans le pli ; 30/09 — une seule colonne vide dépliée (n° 17).

### n° 46 · en vigueur — Le pliage : obligatoire → déplié, facultatif → plié
20/09/2026 · #1095 · l'utilisateur · §0 « Le pliage »
- **Décidé** : la règle se calcule ; un écart exige `exceptionPliage`. Exceptions arbitrées : Au nom de (obligatoire mais pliée), Pièces jointes (facultative mais dépliée). Une valeur autre que le défaut rouvre la section.
- **Pourquoi** : le défaut d'« Au nom de » est juste presque toujours ; les pièces jointes sont le premier geste au téléphone.
- **Écarté** : Destinataires en troisième exception (non `requis`, elle suit la règle).
- **Tenu par** : `npm run lint:etats` (dans les deux sens), `lint:pliage-transmis`.

### n° 47 · en vigueur — Photos et documents : une seule section
20/09/2026 · #1095 · l'utilisateur · §0
- **Décidé** : « Pièces jointes », avec un nom affiché pour une photo comme pour un PDF ; les deux réservoirs restent distincts dans le modèle.
- **Pourquoi** : non écrit.
- **Écarté** : deux sections (écrit « jamais fusionnées » depuis le 17/08).
- **Tenu par** : `SECTIONS_ORDRE`, `lint:etats`.

### n° 48 · en vigueur — Le cadre recomposé ; la section s'appelle « Périmètre »
21/09/2026 · #1095 · l'utilisateur · §0
- **Décidé** : « Champs spécifiques » scindée (Nature, Au nom de, Mise en avant) ; Équipement, Intervenant, Suivi entrent ; Périmètre remonte avant la Description.
- **Pourquoi** : une section à trois intitulés rendait une divergence indéclarable ; « il a fallu plusieurs semaines pour l'UX de Périmètre, ne le casse pas » ; « Qui le voit est une CONSÉQUENCE, la section est Périmètre ».
- **Écarté** : l'intitulé « Qui le voit » (un lot).
- **Tenu par** : `SECTIONS_ORDRE`, `npm run lint:ordre-sections`.

### n° 49 · en vigueur — Un libellé nomme l'objet, et le mot vient de sa déclaration
21/09/2026 · #1107 · non dit · §15
- **Décidé** : « Affaire » et « Actualité » à l'écran (`libelle`, `libelleNouveau`, `libelleModifier`), jamais le nom du modèle.
- **Pourquoi** : le mot de code fuyait jusqu'aux boutons — vingt libellés dans seize fichiers.
- **Tenu par** : `npm run lint:vocabulaire-ecran`, `test_vocabulaire_affaire.py`.

### n° 50 · en vigueur — L'étoile dit l'état du champ
22/09/2026 · #1121 · l'utilisateur, à l'écran · §9
- **Décidé** : `EtoileRequis`, collée au libellé, rouge tant que le champ est vide ; une valeur par défaut active (« Tous ») compte comme une valeur.
- **Pourquoi** : « * rouge, c'est uniquement s'il n'y a aucune valeur » (27/09).
- **Écarté** : l'astérisque tapée ; « (optionnel) ».
- **Tenu par** : `npm run lint:champs`, `e2e/etoile-valeur-defaut.spec.ts`.

### n° 51 · en vigueur — Un seul formulaire d'affaire ; les sections sans objet restent à leur rang
23/09/2026 · non retrouvé · l'utilisateur, sur maquette · §0
- **Décidé** : un seul « + Nouvelle affaire » ; une section qui ne s'applique pas à la nature reste à son rang, atténuée, 🔒 et motif écrit (`inactivePour`) ; ce qu'elle portait ne part pas.
- **Pourquoi** : « un seul “+ Nouvelle affaire”… selon la catégorie, les sections peuvent changer — grisées, pliées, inactives ».
- **Écarté** : les hachures du premier jet (style A retenu sur captures) ; un fond bleu sur la pastille d'en-tête (on la croyait cochée).
- **Tenu par** : `motifInactif()`, `lint:etats`.

### n° 52 · en vigueur — Les titres de section se lisent partout pareil
23/09/2026 · non retrouvé · l'utilisateur, à l'écran · §9 septies
- **Décidé** : la section 1 vit dans `SectionTitre` ; dans une section à plusieurs champs, le libellé se lit un cran sous le titre de section.
- **Pourquoi** : « normalise les titres des sections » ; la hiérarchie se lisait à l'envers.
- **Tenu par** : `npm run lint:section-nommee`.

### n° 53 · révisé — L'ordre des sections se lit dans `SECTIONS_ORDRE`
12/09/2026 · #1095, #1096 · l'utilisateur · §0, §9 sexies
- **Décidé** : l'ordre, les libellés et le nombre ne se lisent que dans `front/src/lib/entites/types.ts` ; `ChampsCommuns` rend les sections communes.
- **Pourquoi** : « Options de publication » n'avait aucun rang ; l'épinglage vivait dans la Diffusion du calendrier.
- **Écarté** : un épinglage dans la Diffusion (une dépendance n'est pas un rang) ; recopier la table ou son compte.
- **Tenu par** : `npm run lint:ordre-sections`, `lint:consignes`.
- **Historique** : 12/09 — Options de publication au rang 3 ; 21/09 — recomposé (n° 48) ; 23/09 — Mise en avant après Destinataires (#1096 : « elles sont complémentaires »). ⚠️ La table du §9 sexies est une copie d'avant le 21/09 : périmée (vérifié dans `types.ts` le 18/10/2026).

### n° 54 · en vigueur — Mouvement et retour au toucher
24/09/2026 · non retrouvé · l'utilisateur, demande · §17
- **Décidé** : jetons de durée et de courbe, aucune durée écrite ; un corps déplié entre en 200 ms ; appui `scale(0.97)` ; animation sans fin réservée à une attente ; survol sous `@media (hover: hover)`.
- **Pourquoi** : essayé sur les Petites annonces (v2.44.0), généralisé le même jour à la demande.
- **Écarté** : `transition: all` ; une hauteur animée.
- **Tenu par** : `npm run lint:mouvement`, `lint:animations-infinies`, `lint:survol`.

### n° 55 · en vigueur — Les destinataires : la nomenclature
25/09/2026 · #1301, #1311, #1436 · l'utilisateur · §2 bis
- **Décidé** : libellés au pluriel ; « Tous », jamais « Tous les résidents » ; un résident habite (occupant ou locataire). « Résident concerné » entre Locataires et Conseil syndical ; chaque catégorie d'affaire a son défaut.
- **Pourquoi** : « Tous les résidents était faux, car un copropriétaire bailleur ou un bailleur n'est pas résident ».
- **Écarté** : renommer le code `résidents` (une migration) ; retirer la pastille « Conseil syndical » (26/09, à l'écran : trois degrés de restriction, pas un doublon).
- **Tenu par** : `test_libelle_tous.py`, `test_lecture_pastille.py`, `npm run lint:lecture`, `e2e/destinataires-panne.spec.ts`.

### n° 56 · en vigueur — Le NEW rouge, partout
26/09/2026 · non retrouvé · l'utilisateur · §3
- **Décidé** : `BadgeNouveau` dit « NEW », en rouge, fixe.
- **Pourquoi** : non écrit — seule trace : la mention en §3, où une maquette d'affaires ne l'a pas défait (10/10).
- **Écarté** : « Nouveau ».
- **Tenu par** : aucun garde-fou nommé.

### n° 57 · en vigueur — Un message : deux régimes
26/09/2026 · non retrouvé · non dit · §17
- **Décidé** : un message simple va au coin fixe (`Toast`) ; la suite d'un geste naît de l'élément (bulle ancrée). 23/10/2026 (#2168) : une erreur reste jusqu'à ce qu'on la ferme.
- **Pourquoi** : une place prévisible pour l'un, l'origine du geste pour l'autre (`emil-design-eng`) ; partie en 4 s, une erreur n'était lue que par qui regardait (WCAG 2.2.1, audit `apple-design`).
- **Tenu par** : `e2e/toast.spec.ts` (l'erreur reste, le survol retient la réussite).

### n° 58 · en vigueur — Une recherche libre remplace le filtre « Catégorie »
27/09/2026 · #1397 (v2.72.0) · l'utilisateur, sur maquette · §5 bis
- **Décidé** : la règle est au serveur et ne lit que ce que l'écran montre ; la carte dit où le mot a été trouvé ; les Archives sur demande.
- **Pourquoi** : maquette A, avec l'extrait et les Archives de la C — https://claude.ai/artifact/BRYAWNn4EZAx1EBTHHNMQu
- **Écarté** : le filtre par catégorie ; une seconde règle de recherche à l'écran.
- **Tenu par** : `test_recherche_affaires.py`, `recherche_affaires.py --selftest`.

### n° 59 · en vigueur — La charte : tailles de texte et couleurs d'état
27/09/2026 · #1055 · l'utilisateur, sur maquette · §18
- **Décidé** : une taille hors échelle se range au cran supérieur ; un état prend son jeton et ses dérivés ; `--color-warning` ne sert jamais au texte.
- **Pourquoi** : posé par l'utilisateur comme règle de tout le projet — https://claude.ai/artifact/5EUqnbiH4HSF8wJe4khAgP
- **Écarté** : les teintes de Tailwind ; rétrécir un texte.
- **Tenu par** : `npm run lint:charte-valeurs`, `lint:badge`, `lint:encart-avertissement`, `lint:texte-avertissement` (#2167).

### n° 60 · en vigueur — L'auteur d'une idée ou d'un sondage ne s'affiche jamais
27/09/2026 · #1373 · non dit · §3
- **Décidé** : leurs cartes ne nomment pas l'auteur ; la petite annonce nomme le sien.
- **Pourquoi** : leurs API ne l'exposent pas, et l'exposer serait une décision de données personnelles.
- **Tenu par** : `npm run lint:pastilles`.

### n° 61 · en vigueur — La correction d'une Suite rouvre toutes ses sections
01/10/2026 · non retrouvé · l'utilisateur · §0
- **Décidé** : Suivi compris ; elle corrige l'entrée à sa date, jamais une étape de plus ; sans Diffusion.
- **Pourquoi** : « l'édition d'une suite doit permettre de modifier toutes les sections éditables et surtout le suivi ».
- **Tenu par** : `test_correction_suite.py`, `e2e/correction-suite.spec.ts`.

### n° 62 · en vigueur — « À traiter » : un onglet d'admin, sans redirection des anciennes clés
01/10/2026 · non retrouvé · non dit · §9
- **Décidé** : comptes en attente, commandes d'accès, demandes de profil en sections d'un même onglet ; une file de plus s'y ajoute comme section.
- **Pourquoi** : non écrit.
- **Écarté** : rediriger `comptes`, `acces`, `demandes_profil` (les liens de l'API ont été corrigés à la place).
- **Tenu par** : `test_liens_front.py`, `npm run lint:routes`.

### n° 63 · remplacé par n° 66 — L'affaire dépliée AU FIL : maquette A
15/10/2026 · non retrouvé · l'utilisateur, sur maquette · §3 « L'affaire DÉPLIÉE au fil »
- **Décidé** : au fil, « Dernière mise à jour » · « Synthèse » · « Demande initiale » pliée (`FluxRubriquesAffaire`) ; chaque rubrique porte ses pièces.
- **Pourquoi** : sur TK-109008, les photos de la clôture s'affichaient sous le texte de la demande, sans dire d'où elles venaient.
- **Écarté** : quatre autres maquettes.
- **Tenu par** : `test_flux_affaire_rubriques.py`, `e2e/fil-rubriques-affaire.spec.ts`.
- **Historique** : ⚠️ le n° 20 (16/10) dit remplacer la maquette A ; le code (18/10/2026) rend G sur la carte (`CorpsCarteTicket`) et **A au fil** (`FluxCorps`). Une même affaire dépliée avait donc deux rendus. 18/10 — arbitré : n° 66.

### n° 64 · en vigueur — La synthèse enrichit la carte, elle ne la date pas
15/10/2026 · non retrouvé · non dit · §3
- **Décidé** : la Suite `synthese` n'est pas une candidate du fil.
- **Pourquoi** : validée un ou deux jours après la clôture, l'affaire remonterait en tête et se lirait comme une nouvelle panne.
- **Tenu par** : `test_flux_affaire_rubriques.py`.

### n° 65 · en vigueur — Le lien d'une affaire rend SA CARTE, dépliée
15/10/2026 · non retrouvé · l'utilisateur, à l'écran · §13
- **Décidé** : `/tickets/[id]` rend `ListeTickets` sur une liste d'une affaire, dépliée, avec les gestes de la liste ; reste propre : le fil de messages.
- **Pourquoi** : « affichée d'une manière différente du fil d'actualité ou de la page ».
- **Écarté** : une fiche de détail à part (en-tête, boutons d'état, Historique).
- **Tenu par** : `e2e/lien-affaire-depliee.spec.ts`.

### n° 66 · en vigueur — L'affaire dépliée a UN rendu ; le fil s'ouvre sur « La suite »
18/10/2026 · v3.4.0 (#2078) · l'utilisateur, sur recommandation · §3
- **Décidé** : la brique des trois étapes (`RubriqueEtape`, n° 20) rend l'affaire dépliée partout, fil d'activité compris ; seule l'étape dépliée par défaut dépend du contexte — « La demande » dans la liste, **« La suite »** au fil.
- **Pourquoi** : un objet, un rendu (n° 65) ; et le fil montre d'abord ce qui vient d'arriver, ce que la maquette A (n° 63) faisait bien.
- **Écarté** : le fil en G à l'identique, ouvert sur la demande (l'actualité passerait derrière elle) ; garder A au fil en déclarant la divergence (deux composants, deux allures).
- **Tenu par** : `e2e/fil-rubriques-affaire.spec.ts` — la même affaire lue au fil et dans la liste a les mêmes étapes (titres, ordre, teintes, résumés) ; seule l'ouverture par défaut diffère.
- **Historique** : 18/10 — arbitré, maquette validée à l'écran. 20/10 — livré (v3.4.0, #2078) : `FluxAffaireEtapes` charge l'affaire et son fil à l'ouverture, `FluxRubriquesAffaire` est retiré, aucun changement d'API. L'affichage reste à constater en production.

### n° 67 · en vigueur — Après « Enregistrer » un CR, l'affaire suivante s'ouvre, son titre en haut
20/10/2026 · #2082 · l'utilisateur · §3
- **Décidé** : au point CS / Syndic, enregistrer le compte rendu d'une affaire déplie la ligne suivante du tableau et place son titre en haut de l'écran, mesuré après le repli de la précédente (`amenerEnHaut`).
- **Pourquoi** : « c'est très perturbant de perdre le fil des affaires […] fait perdre du temps à rechercher l'affaire suivante ».
- **Écarté** : rester sur place, rien d'ouvert (proposé, refusé).
- **Tenu par** : `e2e/point-conseil.spec.ts`.

### n° 68 · remplacé par n° 71 — Vignette Public / Privé : Privé = lue du CS et du syndic seuls
20/10/2026 · #2082 · l'utilisateur · §3
- **Décidé** : chaque affaire du reporting (tableau, PDF, relecture) porte « Public » ou « Privé » ; Privé quand aucun compte hors du conseil et du syndic ne la lit, auteur résident compris — calculé au serveur par `ticket_visible` (`lecteurs_du_conseil`).
- **Pourquoi** : « Privé = CS & Syndic / Public = tout autre cas ».
- **Écarté** : Privé quand seul l'auteur résident la lit en plus du conseil.
- **Tenu par** : `test_points_conseil_etats.py`.

### n° 69 · en vigueur — L'état décidé au point ne s'applique qu'à la validation ; « À l'AG » reste à l'AG
20/10/2026 · #2082 · l'utilisateur · §3
- **Décidé** : la saisie d'un CR montre l'état actuel et l'« état à la validation » — « Chez le syndic » d'office pour une affaire ouverte, son état sinon ; posé par une Suite d'état à la validation seulement ; une affaire close ailleurs n'est pas rouverte.
- **Pourquoi** : « offrir la possibilité de changer l'état à la validation du CR (pas avant) » ; « si une affaire a son suivi à AG, ne pas par défaut la mettre à Chez le syndic ».
- **Tenu par** : `test_points_conseil_etats.py`.

### n° 70 · en vigueur — Affaires liées : rassemblées, la plus ancienne absorbe et reste ouverte
20/10/2026 · #2083 · l'utilisateur · §3
- **Décidé** : au Suivi des affaires, les affaires liées se suivent sous une ligne « n affaires liées » ; « Fusionner » (titre et description proposés par l'assistant, relus) fait absorber les autres par la plus ancienne, qui garde son numéro et reste ouverte ; « Ne pas fusionner » rend le tri par ancienneté et tait la fusion à la clôture.
- **Pourquoi** : demandé le 19/10/2026 ; « la plus ancienne absorbe » choisi parmi deux options le 20/10.
- **Écarté** : une affaire neuve qui absorberait les deux.
- **Tenu par** : `test_fusion_en_cours.py`, `e2e/suivi-affaires.spec.ts`.

### n° 71 · en vigueur — Au reporting, l'affaire dit son état de suivi et « qui la lit » comme sur la page Affaires
20/10/2026 · #2089 · l'utilisateur · §3
- **Décidé** : sous le titre de chaque affaire du Suivi (tableau, CR global, relecture, PDF), l'état de suivi en vignette et la pastille « qui la lit » de la page Affaires (`PastilleLecture`) ; au PDF, son mot, calculé par la règle du serveur (`lecture_affaire`).
- **Pourquoi** : « la vignette Privé/public n'est pas un bon choix : reprendre l'objet destinataires tel qu'il apparaît sur la page affaire ».
- **Écarté** : la vignette Public / Privé (n° 68).
- **Tenu par** : `test_lecture_affaire.py`.

### n° 72 · en vigueur — Le PDF du point : la maquette B, et « Exporter en PDF » le tire pendant un point
20/10/2026 · #2089 · l'utilisateur, sur maquette · §3
- **Décidé** : le rapport « Exporter en PDF » du Suivi, augmenté : le point (Quand / Où / Qui) et un cartouche de validations en tête, chiffres et répartitions, chaque affaire abordée avec son résumé d'origine puis son CR dans la cellule, les non abordées à la fin ; pendant un point, « Exporter en PDF » rend ce document ; « Aperçu PDF » est retiré.
- **Pourquoi** : « reprendre uniquement celui de “exporter PDF” qui est chouette » ; B choisie parmi cinq maquettes, « bien conserver les résumés initiaux de chaque affaire après le titre ».
- **Écarté** : A (rapport puis CR en bande), C (deux colonnes), D (fiches), E (procès-verbal) ; le PDF de la v3.2.0 sans résumé ni âge.
- **Tenu par** : `test_points_conseil_expedition.py`.

### n° 73 · en vigueur — L'affaire dépliée : La demande, La suite, Comptes rendus, La synthèse
21/10/2026 · non retrouvé · l'utilisateur · §3
- **Décidé** : les étapes d'une affaire dépliée se suivent toujours dans cet ordre — La demande · La suite · Comptes rendus (s'il y en a de validés) · La synthèse (si l'affaire close en a une) —, dans la liste Affaires comme au fil (`CorpsCarteTicket`, n° 66).
- **Pourquoi** : « adopte l'ordre suivant des sections (mémorise-le) » — c'était déjà l'ordre rendu (#2042), jamais écrit comme une décision.
- **Tenu par** : `e2e/fil-rubriques-affaire.spec.ts` (mêmes titres, même ordre au fil et dans la liste) — aucun contrôle ne fige l'ordre lui-même.

### n° 74 · en vigueur — Toute affaire close reçoit sa synthèse, quelle que soit sa catégorie
21/10/2026 · non retrouvé · l'utilisateur, sur recommandation · §3
- **Décidé** : une affaire résolue ou annulée — à sa carte, par une Suite ou à la validation d'un point CS / Syndic — reçoit sa synthèse IA une demi-heure plus tard, toutes catégories ; seule l'annexe vide d'un point, annulée d'office, n'en reçoit pas. Le carnet ne range toujours que les catégories du bâti. Les affaires closes par un point déjà validé ont été rattrapées (migration 0306).
- **Pourquoi** : une question et une nuisance closes au point du 19/10/2026 n'ont pas eu de synthèse, et l'utilisateur l'a lu comme une anomalie : « la clôture d'une affaire doit lancer le traitement IA de synthèse ». Remplace « uniquement les affaires du carnet sont éligibles » (03/10/2026, #1643).
- **Écarté** : le carnet, plus toute affaire close en point (deux règles : une même question aurait une synthèse close en point, aucune close depuis sa carte).
- **Tenu par** : `test_synthese_eligibilite.py`, `test_points_conseil_etats.py`.

### n° 75 · en vigueur — Admin rangé par niveau : six groupes, deux rangées
21/10/2026 · #2062 · l'utilisateur, sur maquette · §4, §9
- **Décidé** : six groupes aux noms inchangés — 👥 Personnes, 📥 Imports, 🏢 Copropriété, 🔌 Services, 🎨 Présentation, 🛠 Exploitation ; variante A : une rangée de groupes, puis les onglets du groupe actif (`BarreOnglets`) ; l'Exploitation visible de l'administrateur ET de l'opérateur, ce sont ses onglets qui se réservent (Installation et Installations à l'opérateur, Maintenance aux deux) ; un seul onglet Imports, la source en pastilles ; « Paramétrage site » scindé en Copropriété › Fonctionnement et Présentation › Connexion et pied de page ; chaque ancienne adresse `?onglet=` reste servie.
- **Pourquoi** : dix-neuf onglets en deux rangées sans ordre de niveau ; maquette validée le 21/10/2026, avec la correction de la relecture (un groupe Exploitation caché à l'administrateur lui aurait retiré Maintenance).
- **Écarté** : la variante B (colonne au bureau, sélecteur au téléphone : un composant neuf) ; trois onglets d'import ; l'Exploitation réservée à l'opérateur.
- **Tenu par** : `e2e/admin-groupes.spec.ts`, `npm run lint:onglets-reserves`, `npm run lint:routes`.
