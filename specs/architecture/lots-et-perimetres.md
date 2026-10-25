# Lots, circulations et périmètres — la règle générale

> **Statut** : spécification de conception, sans code. Elle vaut pour **toute copropriété** :
> elle ne contient aucune donnée d'une copropriété précise. Les relevés tirés d'un règlement
> réel (liste des lots, tantièmes, propriétaires) restent **en local, jamais versionnés** — le
> dépôt est public. Les exemples ci-dessous sont **fictifs**.
>
> Source de la règle : le règlement de copropriété (RCP) — état descriptif de division,
> tableaux de répartition des charges, actes modificatifs. La transcription d'un RCP ne se
> substitue pas à l'acte authentique. Les travaux dérivés vivent dans les issues GitHub
> (épopée « Lots, circulations et périmètres »).

## 1. La règle : trois rattachements indépendants

Dans un règlement de copropriété qui comporte des parkings et des caves en sous-sol, **un
emplacement ou une cave n'est rattaché ni à son propriétaire, ni au bâtiment où celui-ci
habite : il est rattaché à la circulation verticale qui le dessert** — l'ascenseur et
l'escalier par lesquels on rejoint le sous-sol depuis la surface. L'état descriptif le dit
dans une colonne (souvent « ASCEN » ou « desserte ») ; le tableau de répartition des charges
de chaque bâtiment en tire des tantièmes d'**ascenseur** et d'**escalier**, distincts des
tantièmes de bâtiment et des tantièmes généraux.

Un lot a donc **trois rattachements**, qu'il ne faut pas confondre :

| Rattachement | Question | Exemple fictif |
|---|---|---|
| **Situé dans** | où est-il construit ? | une place, au 2ᵉ sous-sol du bâtiment « Parking » |
| **Desservi par** | quelle circulation emprunte-t-on pour y aller ? | l'ascenseur et l'escalier du bâtiment 3 |
| **Clés de charges** | à quelles répartitions contribue-t-il, et pour quelle part ? | générale 8/10 000, ascenseur du bâtiment 3 30/10 000, escalier des sous-sols 400/10 000 |

**Exemple fictif.** Un résident du bâtiment 1 détient la place 12. Elle est desservie par le
bâtiment 3 : il paie une part des charges d'ascenseur du bâtiment 3, et il emprunte cet
ascenseur. Ce n'est pas une erreur du syndic, c'est la règle du RCP. Ce qui concerne le
bâtiment 3 — une panne d'ascenseur, un ravalement de cage d'escalier — le concerne donc
aussi. Le hall, le toit et les paliers du bâtiment 3 ne le concernent pas.

Deux conséquences d'ordre général :
- **La circulation décide de ce qui concerne l'occupant**, pas le bâtiment du logement.
- **Un lot peut regrouper deux places** (double emplacement) : c'est un seul lot, avec un
  numéro d'usage « 5 & 6 », une seule quote-part générale, et la même part d'ascenseur qu'une
  place simple.

## 2. Ce qu'un règlement contient, et ce qu'il ne contient pas

| Donnée | Dans le RCP ? | Remarque |
|---|---|---|
| Numéro, bâtiment, nature (logement, commerce, cave, parking, divers), niveau | oui | état descriptif |
| Numéro de porte ou de place | oui | souvent dans le texte de la nature |
| Circulation desservante | oui pour les parkings et caves | colonne dédiée |
| Tantièmes généraux | oui | dénominateur de 10 000 ou 1 000, qui change quand un lot est créé |
| Tantièmes par clé spéciale (bâtiment, ascenseur, escalier) | oui, par bâtiment | tableaux annexes ; un bâtiment à lot unique n'a pas de tableau |
| Clé « stationnements » | la règle, parfois pas les tantièmes | renvoie souvent au cahier des charges d'un syndicat ou d'une association foncière |
| Divisions, fusions, créations de lots postérieures | **non**, sauf s'ils sont versés | actes modificatifs à fournir |
| **Propriétaires, locataires, baux** | **non** | liste du syndic, importée par l'atelier existant |

Règles de prudence : un chiffre douteux (`[?]`) d'une transcription se vérifie sur l'acte et
**n'est jamais corrigé d'autorité** ; la somme des numérateurs d'une clé doit égaler son
dénominateur, sinon l'import s'arrête.

**La numérotation de l'application n'est pas celle de l'acte.** Une application qui compte les
bâtiments « 1, 2, 3 » alors que l'acte dit « A, B, C » (dans l'ordre inverse, parfois) a besoin
d'une correspondance explicite, saisie par l'administrateur — jamais déduite de l'ordre.

## 3. Ce que l'application sait aujourd'hui, et l'écart

| Notion | Modèle actuel | Écart avec la règle |
|---|---|---|
| Lot | `Lot(batiment_id, numero, type ∈ appartement/cave/parking, type_appartement, etage, superficie)` | pas de numéro d'usage ni de niveau de sous-sol ; **pas de circulation desservante** ; pas de tantièmes ; pas de nature « commerce » ni « divers » |
| Parking | `batiment_id` nul (l'import le pose : *le parking n'est pas rattaché à un bâtiment*) | il l'est, par sa circulation |
| Cave | l'import la rattache au bâtiment du logement du même propriétaire | **faux** : une cave est desservie par sa propre circulation |
| Propriété | `UserLot(type_lien, quote_part, actif)` | la quote-part est unique alors qu'un lot a plusieurs clés |
| Périmètre d'un contenu | arbre `perimetre` : `bat:N`, `bat:N/ascenseur`, `parking`… | rien ne relie un **lot** à un **nœud** de l'arbre |
| « Mes bâtiments » (`utils/mes_batiments`) | rattachement + `batiment_id` des lots actifs | un parking n'apporte rien ; une cave apporte le mauvais bâtiment |
| Visibilité (`perimetre_visible`) | un contenu ciblé `bat:N/ascenseur` n'est lu que par « mes bâtiments » ∋ N | le détenteur d'une place desservie par N ne le voit pas |
| Accès (badges, télécommandes) | commandés par lot, portes non modélisées | rien ne dit quels bâtiments un badge doit ouvrir |

## 4. Le modèle cible

Trois ajouts, aucun renommage, tout compatible avec la version précédente
(`test_migrations_compatibles`) :

1. **Le lot porte sa désignation** : `nature` (logement, commerce, cave, parking, divers),
   `numero_usage` (porte ou place, « 5 & 6 » pour un double emplacement), `niveau` (−3 … n),
   `circulation_perimetre_id` → le nœud de l'arbre qui dessert (nul pour un accès direct).
   Un bâtiment porte sa `lettre_rcp`, la lettre ou le numéro de l'acte.
2. **Les clés de charges** : `cle_de_charges(code, libelle, denominateur, perimetre_id)` et
   `quote_part_lot(lot_id, cle_id, numerateur)`. `UserLot.quote_part` cesse d'être saisi
   (second temps, `CONTRACTIONS`) : la quote-part est celle du lot, pas du lien.
3. **Le lot sait quels périmètres le concernent**, dérivés et jamais saisis deux fois :
   `lot_perimetre(lot_id, perimetre_id, relation ∈ situe_dans/desservi_par, derive)`. Dérivation
   (fonction pure) : *situé dans* = le nœud de son bâtiment ; *desservi par* = le nœud de sa
   circulation **et** ses enfants ascenseur et escaliers ; une place ajoute le nœud « parking »,
   une cave ajoute le nœud « caves » de sa circulation. Une ligne posée à la main
   (`derive = faux`) survit à une re-dérivation.

## 5. La visibilité : « mes bâtiments » devient « mes périmètres »

Un contenu ciblé est lu si **l'un de ses périmètres couvre l'un des miens**, « miens » étant
l'union des périmètres de mes lots actifs et de mon rattachement (`perimetres.couvre` porte
déjà le sens : le large englobe l'étroit, jamais l'inverse). Les deux cas zéro actuels sont
conservés. L'axe **public** (`public_cible`, profils documentaires, mandataire) reste combiné
en ET : détenir une place ne donne jamais un droit de lecture qu'on n'a pas adressé.

Cas types (fictifs) :

| Utilisateur | Contenu ciblé | Attendu |
|---|---|---|
| résident du bât. 1, place desservie par le bât. 3 | ascenseur du bât. 3 | visible |
| idem | toit ou hall du bât. 3 | invisible |
| idem | bât. 3 **seul** (sans sous-nœud) | **arbitrage** : `couvre` dit visible |
| résident du bât. 1, cave desservie par le bât. 2 | caves du bât. 2 | visible |
| extérieur, une seule place desservie par le bât. 3 | ascenseur du bât. 3 | visible ; hall et PV du bât. 3 invisibles |
| extérieur, place à accès direct | parking et ses enfants | visible ; aucun bâtiment |
| compte sans rattachement ni lot | tout contenu ciblé | invisible (cas zéro d'accès) |
| documents au périmètre documentaire « bâtiment » | lots **situés dans** le bâtiment | une place *desservie par* lui n'ouvre pas ses PV |

La notification du conseil (`membres_cs_notifiables`) reste inchangée : elle vise le conseil
concerné, pas les payeurs.

## 6. Le copropriétaire extérieur qui n'a qu'une place ou une cave

C'est un **copropriétaire à part entière** : tantièmes généraux, vote, charges générales,
charges de stationnement, ascenseur et escalier de sa circulation. Il n'est pas résident.

| Ressource | Oui | Non |
|---|---|---|
| Convocations, PV, budget, documents « résidence » | ✔ | |
| Contenus à portée globale, parking et ses enfants | ✔ | |
| Contenus de la circulation qui le dessert (ascenseur, escaliers) | ✔ | |
| Hall, paliers, toit, caves, actualités confidentielles du bâtiment | | ✘ |
| Télécommande du portail | ✔ | |
| Badge de hall du bâtiment desservant | **arbitrage** (c'est son chemin piéton) | autres bâtiments ✘ |
| Alerte d'étage, fiche arrivant, « mon logement » | | ✘ |

Aucun rôle ni drapeau nouveau : c'est la règle du §5 appliquée à un compte sans bâtiment.

## 7. Les portes d'un badge suivent « situé dans » et « desservi par »

Un badge ouvre des portes, une télécommande le portail. Règle générale : un occupant d'un
logement ouvre **son** bâtiment ; un détenteur de place ou de cave ouvre **le bâtiment qui la
dessert** (son seul chemin piéton) ; un accès direct n'ouvre aucun hall ; un locataire reçoit
les portes des lots de **son bail**, jamais celles du bailleur. Dans l'application : la
commande propose par défaut les portes dérivées, le conseil valide ou retranche, un constat
signale l'écart (manque ou excès), et l'ajout d'une porte hors dérivation est un geste
journalisé.

## 8. Injecter le règlement dans l'application

Trois chemins, du plus sûr au plus ambitieux :

1. **Un fichier d'état descriptif tenu en local par la copropriété** — jamais versionné —,
   au format de l'atelier d'import existant (`/lots/admin/imports`, tableau de passage
   `lot_import`) étendu : `lot, batiment (lettre), nature, numero_usage, niveau,
   circulation_desservante, une colonne par clé de charges, source`. Pas de propriétaires :
   le rapprochement avec les comptes reste le geste de l'atelier, sur le **numéro de lot**.
2. **Le règlement comme document** déjà versé pour les « Questions au règlement » : sert de
   source citée dans l'écran de chaque lot.
3. **Un usage IA « lire l'état descriptif »** (`llm_usages.USAGES`) : du texte du règlement au
   tableau du chemin 1, avec la page source de chaque ligne et un indice de confiance.
   **Jamais d'écriture directe en base** : la sortie entre dans le tableau de passage, et
   l'administrateur valide ligne à ligne ; les contrôles de somme bloquent une transcription
   fausse. Une autre copropriété obtient ainsi son patrimoine sans ressaisie.

**Contrôles de l'import**, bloquants : somme d'une clé ≠ dénominateur ; lot de l'état
descriptif absent de la liste du syndic (lot sans propriétaire) et l'inverse ; numéro de lot en
double. Un contrôle qui ne peut pas se calculer rend INCONNU, jamais OK. **Un lot peut se
scinder** après le recueil (division ou vente d'un double emplacement) : l'atelier accepte
qu'un numéro devienne deux lignes, garde le lot d'origine en historique, et signale « division
sans acte » tant que l'acte n'est pas versé.

## 9. Les écrans

- **Mon lot → Mes lots et mes espaces** : une carte par lot avec nature, numéro d'usage,
  niveau, « situé dans », « desservi par », ses tantièmes par clé et **la phrase qui explique la
  charge** (« cette place est desservie par l'ascenseur et l'escalier du bâtiment 3 : 30 et 400
  dix-millièmes de leurs charges »). Une pastille « ce qui me concerne » filtre les listes
  d'affaires sur l'union de mes périmètres.
- **Admin › Patrimoine › Lots** : liste par bâtiment et par circulation, lien lot ↔
  propriétaires (atelier existant) et lot ↔ périmètres (dérivé, surchargeable), et les
  **constats** : lots sans propriétaire, propriétaires sans lot, parking ou cave sans
  circulation, clé dont la somme ≠ dénominateur, bâtiment sans lettre, lot hors état
  descriptif, badge sans les portes de ses circulations.
- **Pas d'écran de saisie des tantièmes** : ils viennent de l'import et ne bougent qu'avec un
  acte modificatif ; l'écran les montre et dit leur source.

## 10. Les lots livrables

| # | Lot | Nature | Dépend de |
|---|---|---|---|
| 1 | Modèle : désignation du lot, lettre du bâtiment, clés de charges, lot ↔ périmètres | migration additive, schémas, client | — |
| 2 | Import : atelier étendu, règle des caves corrigée, divisions de lots | atelier existant | 1 |
| 3 | Visibilité : « mes périmètres » ; le copropriétaire extérieur | `mes_batiments`, `perimetre_visible` | 1, 2 |
| 4 | Écran « Mes lots et mes espaces » + pastille « ce qui me concerne » | front | 1, 3 |
| 5 | Admin › Patrimoine › Lots : liste, liens, constats | front + API | 1, 2 |
| 6 | Accès : portes d'un badge | `routers/acces`, constat | 1, 2 |
| 7 | Usage IA « lire l'état descriptif » | `llm_usages`, atelier | 2 |
| 8 | Documentation : glossaire, modèle de données, manuel, FAQ | docs | 1–6 |

## 11. Décisions prises en réalisant (24/10/2026)

Arbitrées par la coordination sur délégation de Philippe du 17/10/2026, consignées
sur l'épopée :

- **Un contenu ciblé sur un bâtiment SEUL n'est pas lu du détenteur d'une place qu'il
  dessert.** Le *desservi par* ne porte que les nœuds de circulation (ascenseur,
  escaliers) et les caves de la circulation — jamais le nœud du bâtiment : sinon ses
  actualités confidentielles s'ouvriraient à un extérieur. Le conseil cible
  l'ascenseur ou l'escalier.
- **Le badge du hall desservant est proposé par défaut** à l'extérieur qui n'a qu'une
  place ou une cave ; le conseil valide ou retranche (§7).
- **Les tantièmes** se lisent par le propriétaire, le bailleur et le mandataire, et par
  le conseil et l'administration ; pas par le locataire
  (`auth/appartenance.lit_les_tantiemes`).
- **Pas de colonne `niveau`** : `Lot.etage` porte déjà les sous-sols — deux colonnes
  pour un fait divergeraient.
- **La table de passage de l'état descriptif est à part** (`ligne_etat_descriptif`),
  et non des colonnes de `lot_import` : les deux fichiers n'ont ni les mêmes états ni
  la même purge. Un seul atelier quand même — l'onglet Imports, source « État
  descriptif ».
- **Ce qui dessert se lit sur l'arbre** : `Perimetre.desserte` (`circulation`,
  `caves`, `stationnement`), administré, posé par le seed sur le gabarit et par la
  migration 0312 sur les bases existantes.
- **Une annexe n'apporte pas son bâtiment** à « mes bâtiments », ni aux documents au
  périmètre « bâtiment ». Mesuré en production avant de l'écrire : aucun compte ne
  tenait un bâtiment de ses seules annexes.
- **Un tantième vide ou nul ne pose pas de part.**
- **La lecture par l'assistant (#2218, 25/10/2026) ne se valide pas ligne à ligne** :
  elle rend le MÊME tableau qu'un fichier, rangé dans la même table de passage, et passe
  par les mêmes contrôles — une somme fausse bloque. Une ligne lue sans certitude porte
  « à vérifier sur l'acte » dans sa source et passe en tête ; un constat *À savoir* la
  relève. Toute la réponse est refusée si une ligne n'a pas de source, si un tantième
  n'est pas entier ou si une clé citée n'est pas déclarée. La lecture tourne en tâche de
  fond (plusieurs minutes, au-delà des 100 s qu'un mandataire laisse) ; l'écran se relit.
  La politique de confidentialité nomme la transmission (migration 0313).
- **« Escalier A' » est une autre clé qu'« Escalier A »** (25/10/2026) : le prime se dit
  en toutes lettres dans le code de la clé (`escalier-a-prime`) ; deux colonnes d'un même
  code sont un bloquant de lecture.
