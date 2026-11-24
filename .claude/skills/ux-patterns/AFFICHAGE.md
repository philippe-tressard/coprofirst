# ux-patterns — Icônes de contexte, périmètre, destinataires (§1 à §2 bis)

Annexe de `SKILL.md`, chargée à la demande (#2910) : la règle d'uniformisation, le
registre des arbitrages, le sommaire et la checklist avant commit sont dans `SKILL.md`.
Les numéros de § sont ceux de toujours : un renvoi « §N » se lit au sommaire.

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
dessus. Le **libellé** d'un lieu ne se compose plus au front (#2633, 11/11/2026) : il
est SERVI. Utiliser :

| Besoin | Où |
|---|---|
| libellé d'un contenu enregistré | le champ servi avec lui — `perimetre_libelle` (et `perimetre_precise_libelle`, `perimetres_libelle`), lu tel quel |
| libellé d'une saisie en cours | `$libellePerimetre(codes, place)` (`#lib/apercu-perimetre.ts`, `POST /perimetres/libelle`) |
| libellé d'UN nœud (le sélecteur) | `perimetreLabelUn(code)` (`#lib/perimetres`) |
| « c'est le périmètre par défaut ? » | `estPerimetreParDefaut(items)` — **remplace** `=== 'résidence'` |
| valeur initiale d'un formulaire | `perimetreDefautListe()` |
| périmètre d'un bâtiment | `perimetreDuBatiment(batimentId)` |
| « concerne tout le monde ? » | `concerneTous(items)` |
| bâtiments visés | `batimentsCibles(items)` |

**Condition d'affichage** : ne jamais afficher le badge si `estPerimetreParDefaut()`
est vrai (c'est le défaut, le redire n'apprend rien).

### Comment un périmètre S'ÉCRIT — trois règles, portées par le serveur (`perimetre_label`, `api/app/utils/perimetres/libelles.py`)

1. **Un espace est qualifié par son parent** — « Bât. 3 › Toit », « AFUL › Voie
   d'accès » — **et le parent par le sien** : « Bât. 1 › Logement › Terrasses Balcons »
   (10/11/2026). Sans cela, le gabarit posant les mêmes neuf espaces sous chaque
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
   stocke l'ordre de sélection ; le serveur trie et regroupe. Un rendu qui
   dépend du chemin de saisie n'est pas un rendu, c'est un hasard.

🔒 **La règle ne s'écrit qu'au serveur** depuis #2633 — l'app iOS lit le même
libellé. `api/tests/test_perimetre_label_batiment.py` l'exécute ;
`npm run lint:regles-partagees` refuse le retour de sa copie au front (qui a été,
jusqu'au 11/11/2026, corrigée d'un seul côté) ; `npm run lint:libelle-perimetre`
exécute ce qui reste au front, le libellé d'un nœud (`perimetreLabelUn`), contre la
même chaîne attendue que le test Python.

**Sélecteur** : `PerimetrePicker.svelte`, alimenté par le store — premier niveau de
pastilles, puis une rangée « Préciser dans … » facultative par niveau ouvert, **trois
niveaux au plus** (10/11/2026 : « Bât. 1 › Logement › Terrasses Balcons »), et la
**description** du nœud affichée sous la sélection. Ce qu'un clic retient et quelles
rangées s'ouvrent se décide dans `#lib/perimetres/selection` — **une** règle, la même
à chaque niveau. L'arborescence elle-même s'arrête au niveau 3 : le serveur refuse tout
geste qui en poserait un quatrième (`utils/perimetres/niveaux`, un regroupement comme
« Bâtiments » ne compte pas).

Rendu — l'icône du périmètre est **🔹**, jamais 📍 (cf. §1), et il s'écrit **une
seule fois** : `<BadgePerimetre libelle={objet.perimetre_libelle} />` (prop
`libelle`, le libellé SERVI ; `""` pour le périmètre par défaut, que le badge tait ;
`ton` en choisit la teinte). Le composant ne compose rien : il porte l'icône — aucune page ne compose son propre
`<span class="badge">` ni son `<p style="…">`. 🔒 `npm run lint:pictogrammes`
refuse le badge 🔹 écrit ailleurs, `lint:styles-en-ligne` l'attribut `style`.
Les trois rendus par page que cette section listait (actualités, calendrier,
tickets) sont tous passés par ce composant ; la page Calendrier n'existe plus
(#1092).

Le libellé vient du serveur — ne jamais réimplémenter la table de correspondance
dans une page (`perimetreLabel`, l'ancienne composition du front, a été retirée le
11/11/2026).

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
  - calcul **unique**, au serveur (`api/app/utils/lecture_pastille`) : servi avec
    l'objet (`lecture`), et pour une saisie par `#lib/apercu-lecture.ts` ;
    `#lib/lecture-ticket.ts` ne garde que ce qu'un écran en lit ; rendu `PastilleLecture` (carte) et badge d'état de
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
    exécuté par `test_lecture_pastille.py` (règle) et `test_lecture_pastille_servie.py`
    (la pastille SERVIE, `utils/lecture_pastille`, #2633). Une règle d'accès qui change
    fait tomber les deux ; le front ne compose plus la pastille, il la lit.
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
