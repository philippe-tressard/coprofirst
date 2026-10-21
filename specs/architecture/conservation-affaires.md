# Conservation des affaires — spécification (#2014)

> **État** : spécification arbitrée le 16/10/2026 sur le feu vert de Philippe. Le lot
> **L1** (constat seul) est livré avec elle ; **L2 et L3** le sont depuis le 17/10/2026,
> la case d'application **coupée**. Les arbitrages sont datés, ceux de la relecture au §9,
> ceux de la livraison au §11.

## 1. Pourquoi

- **RGPD** (art. 5.1.e) : la politique de confidentialité n'annonce **aucune** durée
  pour les affaires, et rien ne les purge. Une durée sans purge est une durée
  fictive (`standards/14`).
- **La place n'est pas le motif.** Mesuré en production le 16/10/2026 : base entière
  17 Mo ; texte des 98 affaires 0,25 Mo ; **pièces jointes des affaires 7 Mo**
  (48 fichiers, ~97 % de leur poids), soit 50 à 100 Mo projetés à dix ans. Les
  115 Mo restants sont les documents de la copropriété, hors de cette spécification.
- **Rien ne presse** : la plus ancienne affaire date du 12/05/2025. La première
  échéance possible tombe à la **fin de l'exercice 2027** (une actualité de 2025, à N+2).

## 2. Le principe — arbitré le 16/10/2026

À l'échéance, une affaire **perd ses pièces jointes et ses auteurs, et garde son
texte**. Les pièces jointes partent dans une archive datée, copiée sur le PC.

Écarté, et pourquoi :

| Écarté | Raison |
|---|---|
| Supprimer l'affaire | le **carnet d'entretien** (décret n° 2001-477) est une VUE sur les affaires closes (`utils/carnet_entretien.py`) : il se viderait |
| Anonymiser aussi le texte libre | aucun outil ne repère un nom de façon fiable ; le promettre serait mentir |
| Une archive qui garde les noms | elle prolongerait la conservation au sens du RGPD : la donnée existerait toujours, ailleurs |
| Une durée unique de dix ans | une panne n'a rien à prouver au-delà de la prescription |

## 3. Les durées

L'échéance se compte en **exercices complets** : une affaire close pendant
l'exercice N échoit au **dernier jour de l'exercice N + durée**.

**L'exercice** (arbitré le 16/10/2026) : l'année civile par défaut, réglable par
copropriété. **Le réglage existe déjà** : `Copropriete.mois_debut_exercice` (1 à 12,
`None` = année civile), servi par `synthese_affaire/agregats.mois_debut_exercice`.
On le réutilise ; on n'en crée pas un second. Son commentaire, qui dit « aucune
autre notion d'exercice n'existe », est mis à jour.

| Durée | Catégories (`CategorieTicket`) | Fondement — *à valider avec le syndic, pas un avis d'avocat* |
|---|---|---|
| **10 exercices** | `etude_travaux`, `sinistre` | garantie décennale (C. civ. art. 1792-4-1) : la preuve d'un désordre ou d'une réserve |
| **5 exercices** | `panne`, `entretien`, `espaces_verts`, `acces_accueil`, `nuisance` | prescription de droit commun (C. civ. art. 2224 ; loi 65-557 art. 42) |
| **2 exercices** | `actualite`, `question`, `bug` | aucune preuve à garder : minimisation des données |

La table vit dans **un seul module**, `utils/conservation_affaires.DUREES`, et un
test refuse une catégorie absente : une catégorie ajoutée sans durée ferait
conserver ses affaires sans limite, sans un mot.

**La date de clôture** : `ferme_le` ; à défaut (une actualité, qui n'a pas de
cycle), la date de publication. Une affaire **ouverte** n'échoit jamais, quel que
soit son âge. Une affaire **fusionnée** (`fusionnee_dans_id`) suit celle qui l'absorbe.

## 4. Ce qui se passe à l'échéance

Une tâche nocturne **par copropriété** (`contexte.pour_chaque_copropriete`,
déclarée dans `TACHES_PERMANENTES`) traite les affaires échues, **un exercice et
un type à la fois**, dans cet ordre — chaque étape ne commence que si la
précédente est prouvée :

1. **L'archive** est écrite (§5), puis **relue** : chaque fichier y figure, avec
   l'empreinte du fichier d'origine. Une archive non vérifiée arrête tout : rien
   n'est retiré.
2. **Les pièces jointes sont retirées du disque**, par `utils/stockage` — celles
   de l'affaire (`photos_urls`, `fichiers_urls`), de son fil
   (`MessageTicket.fichiers_urls`), de ses évolutions
   (`TicketEvolution.fichiers_urls`) et les documents qui lui sont rattachés
   (`Document.ticket_id`). Les colonnes sont vidées dans la même transaction.
3. **Les auteurs sont détachés** : `auteur_id` et `saisi_pour_user_id` de l'affaire,
   `auteur_id` de ses messages et de ses évolutions, et `lot_id` (un lot désigne un
   foyer) ; `contenu_origine` des évolutions (le courriel brut, avec son
   expéditeur) est vidé. À l'écran, l'auteur devient « Un résident » ou « Le
   conseil syndical », selon son rôle au moment de l'échéance. Le périmètre et le
  bâtiment restent.
4. **L'affaire est marquée** : une colonne neuve `conservee_le` (nullable,
   compatible avec la version précédente) date le passage. Elle rend le geste
   idempotent — une affaire marquée n'est jamais retraitée — et l'écran la lit.
5. **Le journal** de maintenance écrit le passage : copropriété, exercice, type,
   nombre d'affaires, de fichiers et d'octets, empreinte de l'archive.

**Restent en base** : le titre, la description, le texte du fil et des évolutions,
les dates, la catégorie, le statut, le périmètre, l'équipement et le contrat
rattachés. Le carnet d'entretien reste donc complet.

**Hors du champ**, avec leur propre durée déjà : les relevés de courriels
(`CONSERVATION_RELEVES_JOURS`), l'historique des envois (90 jours). Les tables
`FilCourriel`, `MessageVerse` et `VersementCourriel` ne portent qu'un
`ticket_id` et des empreintes : rien à détacher, à vérifier en codant.

## 5. L'archive

**Une archive par copropriété, par exercice et par type** —
`affaires-<copropriété>-<exercice>-<type>.zip`, par exemple
`affaires-residence-2026-travaux.zip`. Elle contient :

- les **pièces jointes**, rangées par affaire (`TK-123/photo-1.jpg`…) ;
- un **sommaire** en HTML (lisible sans outil) **et** en CSV (pour un tableur) :
  numéro, titre, catégorie, dates d'ouverture et de clôture, périmètre, équipement
  (`equipement`), contrat et prestataire (`contrat_id`), et la liste de ses fichiers
  avec leur empreinte. Une affaire ne porte pas de coût : le sommaire n'en invente pas ;
- **aucun nom d'auteur** (§2). Les photos peuvent encore montrer des personnes ou
  des intérieurs : c'est assumé et écrit dans la politique (§7).

**Où elle vit sur le serveur** : `prive/archives-affaires/` dans le volume des
fichiers. Ce dossier est **répliqué** par la bascule et **jamais servi** par Caddy
(`handle /uploads/prive/*` répond 404, verrouillé par `test_uploads_prives.py`). Le
seul accès est un téléchargement réservé à l'**administrateur**.

## 6. La copie sur le PC — arbitré le 16/10/2026

Les archives suivent **le même mécanisme que la copie hors site**
(`scripts/poste/export-hors-site.sh`), **sans rotation** : toutes sont conservées
sur le PC, alors que la copie ordinaire n'en garde que `EXPORT_KEEP` (2).

- Le script tire, en plus de la sauvegarde, les archives d'affaires **qu'il n'a
  pas encore**, dans un dossier à part (`$EXPORT_DEST/archives-affaires/`), et
  **vérifie chaque empreinte** contre celle que le serveur annonce.
- Son rapport (`POST /admin/maintenance/rapport`, `tache=export_hors_site`) liste
  les archives copiées et vérifiées. Le serveur les note « copiées le … ».
- Le serveur **retire sa propre copie** d'une archive 30 jours après qu'elle a été
  déclarée copiée et vérifiée — jamais avant. D'ici là, la sauvegarde nocturne la
  porte aussi.
- **Le contrôle** : une archive produite et non copiée depuis plus de 30 jours est
  un constat de **Admin › Maintenance**, et un `WARN` du digest. Comme pour la
  copie hors site : le poste n'est pas toujours allumé, c'est l'âge qu'on surveille.
  Une archive que le serveur ne sait pas lire, ou dont l'empreinte diffère, rend
  INCONNU, jamais OK.

## 7. Ce qui se voit

- **Politique de confidentialité** (`seed/contenus_legaux.py`) : les trois durées,
  et la phrase exacte : *« Au-delà, une affaire est conservée sans ses auteurs ni
  ses pièces jointes ; celles-ci sont archivées hors ligne par le responsable du
  site, sans limite de durée. »*
- **Une affaire conservée** (aux Archives) : un bandeau *« Pièces jointes archivées
  le … — archive 2026, Travaux »* ; les auteurs y lisent « Un résident ».
- **Admin › Maintenance**, bloc *Conservation des affaires* : la prochaine échéance
  et le nombre d'affaires qu'elle touchera, les archives produites (copiées sur le
  PC ou en attente), leur téléchargement, et l'interrupteur du §8.
- **Manuel utilisateur** : les durées et ce qu'il advient d'une affaire ; version
  et date bumpées aux deux emplacements.

## 8. Se tromper sans dégât

Le retrait est **irréversible** sur le serveur : il se livre en deux temps.

1. **Constat seul** (livré en L1) : les échéances se calculent **à la lecture**
   (`GET /admin/conservation-affaires`, `utils/conservation_affaires.constat`) et
   l'écran les montre (« 12 affaires, 31 fichiers, 4 Mo à la fin de l'exercice
   2027 »), sans rien toucher.
2. **Application**, par une case de l'administrateur dans Admin › Maintenance,
   coupée à la livraison. Elle se déclare dans le registre des services
   (`utils/services.SERVICES`), avec ce qu'on perd en la coupant : les durées
   annoncées par la politique redeviennent fictives. Le constat continue, case
   coupée.

## 9. Arbitrages de la spécification — 16/10/2026

1. **Le classement des catégories** du §3 est retenu tel quel : `nuisance` et
   `acces_accueil` à 5 exercices (une nuisance peut finir en litige, prescrit en
   5 ans), `question` à 2.
2. **`lot_id` est détaché** à l'échéance : un lot désigne un foyer. Le périmètre et
   le bâtiment restent, et suffisent au carnet.
3. **Le serveur retire sa copie** d'une archive **30 jours** après qu'elle a été
   déclarée copiée et vérifiée sur le PC.

## 10. Livraison

| Lot | Contenu | Effet en production |
|---|---|---|
| **L1** ✅ | `DUREES`, calcul des échéances, route de constat (admin), carte **Conservation des affaires** d'Admin › Maintenance | aucun : on voit ce qui partira |
| **L2** ✅ | colonne `conservee_le`, tâche nocturne, archive et sommaire, retrait des pièces jointes, détachement des auteurs, case d'application (coupée), politique de confidentialité | aucun tant que la case est coupée |
| **L3** ✅ | copie sur le PC sans rotation, accusé de copie, retrait différé côté serveur, contrôle d'âge | le PC reçoit les archives |

**Garde-fous** : chaque catégorie a sa durée ; les bornes d'exercice
(31/12 et 1/1, et un `mois_debut_exercice` à 7) ; archive vérifiée avant tout
retrait (une archive tronquée n'efface rien) ; idempotence (`conservee_le`) ;
carnet d'entretien intact après le passage ; aucun nom dans le sommaire ; fichiers
d'une autre copropriété jamais touchés (`test_etancheite_coproprietes.py`) ;
migration compatible (`test_migrations_compatibles.py`).

## 11. Arbitrages de la livraison — 17/10/2026

1. **La politique de confidentialité change le jour où la case est cochée**, pas à la
   livraison de L2 : tant qu'elle est coupée, rien n'est appliqué, et annoncer les
   durées les rendrait fictives (`standards/14`). Cocher la case est donc un geste en
   deux temps — la phrase du §7 entre dans la politique (migration de texte livré),
   puis la case se coche. Proposé à Philippe le 17/10/2026, sur son feu vert à L2-L3.
2. **La case est un service** (`utils/services.SERVICE_CONSERVATION`), coché dans
   Administration › Services et nulle part ailleurs ; la carte de Maintenance dit son
   état et y renvoie. Elle est **hors bail** (`SERVICES_HORS_BAIL`) : c'est
   l'obligation de la copropriété, que la référence n'a pas à accorder.
3. **L'auteur détaché garde sa qualité** (`auteur_qualite` : « resident », « conseil »),
   rendue par `utils/noms.nom_auteur` ; un compte déjà supprimé reste « Ancien résident ».
   Le « saisi pour » d'une personne extérieure (nom, adresse) part avec les auteurs.
4. **Un document rattaché part avec son fichier** (la ligne `Document` est supprimée) :
   le sommaire garde son nom et son empreinte.
5. **Le bandeau d'une affaire conservée** ne dit pas l'exercice ni le type de son
   archive : « 🗄️ Conservée le … » suffit au lecteur, l'archive se retrouve par
   Maintenance (`MentionConservation`).
6. **Une affaire échue sans pièce jointe** est détachée sans archive.
7. **L'accusé du poste** passe par sa propre route à clé
   (`POST /admin/maintenance/archives-affaires/copiees`), pas par le rapport de la
   copie hors site : le rapport reste celui de la sauvegarde ; une empreinte qui
   n'est pas celle du serveur n'accuse rien.
8. **Le contrôle d'âge** est un constat du contrôle de santé du matin
   (`conservation_copie.archives_en_retard`), qui part par courriel comme la copie
   hors site périmée.

## 12. Réalisation de l'arbitrage 1 du §11 — 21/10/2026

La phrase du §7 n'entre pas par une migration (elle serait servie case coupée, donc
fictive) : `PUT /config` l'insère **au passage de la case à « 1 »**
(`utils/conservation_politique.apres_ecriture`), devant la ligne « Tokens de
rafraîchissement » de la section 5, **une seule fois**, composée de `DUREES` et de leur
fondement (`seed/contenus_legaux_conservation`). Un texte retouché dont l'ancre a
disparu n'est pas réécrit : le constat (`politique_annonce`) et la carte de Maintenance
le disent. Décocher ne la retire pas (ce qui a été archivé reste vrai). Le texte
modifié repasse « à relire » (empreinte). 🔒 `test_conservation_politique.py`.
