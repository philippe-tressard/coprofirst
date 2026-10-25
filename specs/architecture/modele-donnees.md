# Modèle de données

> Entités principales déduite de la description du projet (personas, cas d'utilisation, arborescence).  
> ORM : SQLModel (SQLAlchemy + Pydantic). Migrations : Alembic (migrations idempotentes — chaque script vérifie l'existence des tables/colonnes avant création). Base : PostgreSQL.  
> **Note d'implémentation :** Alembic est la seule source de vérité pour la structure des tables. `SQLModel.metadata.create_all()` n'est pas appelé au démarrage — toutes les modifications de schéma passent par un fichier de migration versionnée.

---

## Entités

### Copropriété

> Configuration de l'immeuble, modifiable par l'admin uniquement (EF-WEB-014). Constitue le support numérique du carnet d'entretien obligatoire (Art. L. 731-2 CCH, Décret 2001-477).

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | Identifiant |
| nom | string | « Résidence du Parc » |
| adresse | string | « 5 boulevard Fernand Hostachy » |
| ville | string | « Croissy-sur-Seine » |
| code_postal | string | « 78290 » |
| annee_construction | integer | Année de construction (ex. 1975) |
| nb_lots_total | integer | Nombre total de lots de la copropriété |
| numero_immatriculation | string | N° registre national des copropriétés ANAH — obligation Loi ALUR |
| assurance_compagnie | string | Nom de l'assureur multirisques immeuble |
| assurance_numero_police | string | Numéro de police d'assurance |
| assurance_echeance | date | Date d'échéance du contrat d'assurance |
| photo_url | string | Photo de la résidence (optionnel) |

### Bâtiment

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | Identifiant |
| copropriete_id | FK Copropriété | — |
| numero | integer | 1 à 4 |
| nb_etages | integer | RDC + 3 étages (= 4 niveaux) |
| sous_sol | string | Description des niveaux -1 / -2 |
| specificites | string | Ex. jardin collectif + local vélo (bât. 4) |
| lettre_rcp | string, nullable | La lettre ou le numéro que le règlement donne au bâtiment ; saisie, jamais déduite (`lots-et-perimetres.md`) |

### Périmètre  *(arborescence : où se situe une demande)*

Remplace la table de libellés qui était écrite en dur dans `api/app/utils/perimetres.py`
et recopiée dans `front/src/lib/utils.ts` avec un contenu différent. **Aucun code de
périmètre n'existe plus dans le code** : l'arborescence est entièrement reconstructible
depuis l'administration, ce qui permet de servir une copropriété sans AFUL ni caves.

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | Identifiant |
| code | string unique | Ce qui est stocké dans les contenus (`résidence`, `bat:2`, `bat:2/hall`). **Immuable après création** : le modifier orphelinerait les contenus déjà publiés |
| parent_id | FK Périmètre | Nullable — les nœuds de premier niveau n'ont pas de parent |
| libelle / libelle_court | string | « Hall d'entrée » / « Hall » (badges) |
| description | string | Ce que le périmètre couvre, qui le voit, qui est notifié |
| icone | string | Nom d'icône Lucide, nullable |
| batiment_id | FK Bâtiment | Nullable — porté par les nœuds de bâtiment ; les descendants l'héritent par remontée d'arbre |
| portee_globale | boolean | Concerne tous les résidents. Remplace la liste `SCOPES_RESIDENCE`, qui existait en trois exemplaires |
| selectionnable | boolean | Un nœud de regroupement ne se cible pas ; sert aussi à retirer un périmètre de la saisie sans casser l'historique |
| ordre / actif | integer / boolean | Tri, suppression logique |
| modifie_par_id / modifie_le | FK Utilisateur / datetime | Traçabilité — `portee_globale` est une décision de sécurité |

**Règles de résolution** (`api/app/utils/perimetres.py`, seul module à parcourir l'arbre) :

- un nœud est à portée globale si lui **ou l'un de ses ancêtres** l'est ;
- le bâtiment visé est celui du nœud, ou du **plus proche ancêtre** qui en porte un ;
- un code introuvable — nœud supprimé, arbre vidé, table illisible — **n'accorde rien** :
  un contrôle qui ne peut pas s'exécuter ne renvoie jamais OK (`standards/04`).

⚠️ À ne pas confondre avec `Document.perimetre` et `CategorieDocument.perimetre_defaut`
(`résidence` \| `bâtiment` \| `lot`), qui portent le même nom mais répondent à une autre
question : non pas *où* se passe une demande, mais *qui a le droit de lire* un fichier.
Les deux axes restent distincts.

### Lot

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | Identifiant |
| batiment_id | FK Bâtiment | — |
| numero | string | Numéro de lot |
| type | enum | `appartement` \| `cave` \| `parking` |
| type_appartement | enum | `studio` \| `T1` \| `T2` \| `T3` \| `T4` \| `T5` (si appartement) |
| etage | integer | Le niveau, sous-sols compris (−2 pour une place au 2ᵉ sous-sol) ; il n'y a pas de colonne `niveau` à part |
| nature | enum, nullable | `logement` \| `commerce` \| `cave` \| `parking` \| `divers` — l'état descriptif ; vide tant qu'il n'est pas importé, lue par `utils/designation_lot.nature_du_lot` |
| numero_usage | string, nullable | La porte ou la place (« 5 & 6 ») |
| circulation_perimetre_id | FK Périmètre, nullable | Le nœud (bâtiment) dont la circulation dessert le lot ; nul = accès direct |

### CléDeCharges · QuotePartLot · LotPérimètre *(la désignation du règlement, #2212)*

| Table | Champs | Rôle |
|-------|--------|------|
| `cle_de_charges` | code, libelle, denominateur, perimetre_id?, ordre | une répartition du règlement |
| `quote_part_lot` | lot_id, cle_id, numerateur — unique (lot, clé) | les tantièmes d'un lot dans une clé |
| `lot_perimetre` | lot_id, perimetre_id, relation (`situe_dans` \| `desservi_par`), derive | les périmètres d'un lot, **dérivés** (`utils/perimetres/lots`), une ligne manuelle (`derive = faux`) survit |
| `import_etat_descriptif` · `ligne_etat_descriptif` | — | la table de passage de l'état descriptif |

`Perimetre.desserte` (`circulation` \| `caves` \| `stationnement`) dit ce qu'un nœud dessert. **Règle de visibilité** : un contenu ciblé est lu si son bâtiment est l'un des miens (rattachement, logements — jamais une annexe), ou s'il est ciblé sous un nœud qui dessert l'un de mes lots ; la table des cas est dans `lots-et-perimetres.md` §5.

### Utilisateur

| Champ | Type | Description |
|-------|------|--------------|
| id | integer PK | Identifiant |
| nom | string | — |
| prenom | string | — |
| email | string UNIQUE | — |
| telephone | string | — |
| hashed_password | string | Nullable — hash bcrypt |
| statut | enum | `copropriétaire_résident` \| `copropriétaire_bailleur` \| `locataire` \| `syndic` \| `mandataire` |
| role | enum | `résident` \| `conseil_syndical` \| `admin` — rôle principal (legacy + fallback) |
| roles_json | string | Rôles cumulés séparés par virgule — ex. `résident,conseil_syndical` |
| societe | string | Nullable — Nom de la société (obligatoire pour syndic & mandataire) |
| fonction | string | Nullable — Fonction (obligatoire pour syndic & mandataire) |
| photo_url | string | Optionnel — URL de la photo de profil |
| actif | boolean | Compte validé par le CS |
| onboarding_complete | boolean | Assistant d'accueil terminé |
| onboarding_etape | integer | Étape en cours de l'assistant (0–4) |
| consentement_rgpd | boolean | Consentement à la politique de confidentialité (case à cocher non pré-cochée) |
| consentement_communications | boolean | Consentement opt-in aux communications d'actualités (distinct, non pré-coché) |
| sondage_interdit | boolean | Admin peut bloquer la participation aux sondages |
| cree_le | datetime | — |

### UserLot *(association propriétaire ↔ lot et locataire ↔ lot)*

> Un lot peut être possédé par **plusieurs copropriétaires** (ex. conjoints). La table `UserLot` modélise à la fois les propriétaires et les occupants d'un lot.

| Champ | Type | Description |
|-------|------|-------------|
| user_id | FK Utilisateur | — |
| lot_id | FK Lot | — |
| type_lien | enum | `propriétaire` \| `locataire` |
| quote_part | decimal | Quote-part de copropriété en tantièmes (nullable, propriétaires uniquement) |

### Mandat *(lien mandataire ↔ copropriétaire bailleur)*

> Permet de savoir quel mandataire représente quel copropriétaire bailleur, et donc de le notifier lors des tickets de ses locataires.

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| mandataire_id | FK Utilisateur | Utilisateur avec `statut = mandataire` |
| bailleur_id | FK Utilisateur | Copropriétaire bailleur représenté |
| lot_id | FK Lot | Lot concerné par le mandat |
| type_mandat | enum | `location` \| `juridique` |
| date_debut | date | Début du mandat |
| date_fin | date | Nullable — mandat à durée indéterminée si null |

### Vigik

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| code | string | Référence physique du badge |
| lot_id | FK Lot | Lot associé |
| user_id | FK Utilisateur | Détenteur actuel |
| statut | enum | `actif` \| `suspendu` \| `perdu` |
| perimetre_cible | JSON, nullable | Ce que le badge **ouvre** : codes de périmètre (la copropriété, des bâtiments, les portillons). `null` = « on ne sait pas » (#953), jamais « tout » |
| cree_le | datetime | — |

**Les portes d'un badge** (#2217) : celles que ses lots justifient se **dérivent** (`utils/acces_portes`) — le bâtiment d'un logement, le bâtiment de la circulation qui dessert une place ou une cave, rien pour une place en accès direct ; un badge remis au locataire, par ses seuls lots. Elles ne sont que **proposées** au conseil, qui les reprend ou non : `perimetre_cible` ne s'écrit que par un geste du conseil (journalisé, `acces_perimetre_pose`) ou, en silence, par la règle de #953 (`utils/acces_perimetre`). Le constat `utils/acces_constats` signale le manque et l'excès, jamais bloquant.

### Télécommande

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| code | string | Référence physique |
| lot_id | FK Lot | — |
| user_id | FK Utilisateur | Détenteur actuel |
| statut | enum | `actif` \| `suspendu` \| `perdu` |
| cree_le | datetime | — |

### CommandeAccès *(demande de vigik ou télécommande)*

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| user_id | FK Utilisateur | Demandeur |
| type | enum | `vigik` \| `télécommande` |
| motif | string | — |
| statut | enum | `en_attente` \| `acceptée` \| `refusée` |
| commentaire | string | Motif de refus ou note |
| cree_le | datetime | — |

### Ticket *(demande / signalement)*

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| auteur_id | FK Utilisateur | — |
| categorie | enum | `panne` \| `nuisance` \| `question` \| `urgence` |
| titre | string | — |
| description | text | — |
| statut | enum | `ouvert` \| `en_cours` \| `résolu` \| `annulé` \| `fermé` |
| priorite | enum | `normale` \| `haute` \| `urgente` |
| batiment_id | FK Bâtiment | Optionnel |
| lot_id | FK Lot | Optionnel |
| cree_le | datetime | — |
| mis_a_jour_le | datetime | — |

### MessageTicket *(échange sur un ticket)*

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| ticket_id | FK Ticket | — |
| auteur_id | FK Utilisateur | — |
| contenu | text | — |
| cree_le | datetime | — |

### Publication *(actualités, affichage, idées, sondages)*

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| auteur_id | FK Utilisateur | — |
| type | enum | `actualité` \| `affichage` \| `idée` \| `sondage` |
| titre | string | — |
| contenu | text | — |
| perimetre | enum | `résidence` \| `bâtiment` |
| batiment_id | FK Bâtiment | Si périmètre = bâtiment |
| publie_le | datetime | — |
| epingle | boolean | Affichage prioritaire |

### Sondage

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| publication_id | FK Publication | — |
| question | string | — |
| cloture_le | datetime | — |

### OptionSondage

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| sondage_id | FK Sondage | — |
| libelle | string | — |

### VoteSondage

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| sondage_id | FK Sondage | — |
| option_id | FK OptionSondage | — |
| user_id | FK Utilisateur | — |

### Prestataire

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| nom | string | — |
| specialite | string | Ex. plomberie, ascensoriste |
| telephone | string | — |
| email | string | — |

### Mission *(ordre de mission ou contrat)*

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| prestataire_id | FK Prestataire | — |
| titre | string | — |
| description | text | — |
| type | enum | `ponctuelle` \| `maintenance` |
| statut | enum | `en_cours` \| `terminée` \| `annulée` |
| montant | decimal | — |
| batiment_id | FK Bâtiment | Optionnel |
| cree_le | datetime | — |

### ContratEntretien  *(carnet d'entretien — contrats récurrents)*

> Représente un contrat de maintenance en cours pour un équipement collectif. Distinct de `Mission` (ordre ponctuel) : ici il s'agit d'un contrat pluriannuel ou à durée indéterminée. Géré par l'admin (EF-WEB-014), visible par les résidents en lecture.

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| copropriete_id | FK Copropriété | Toujours renseigné |
| batiment_id | FK Bâtiment | Nullable — si le contrat est spécifique à un bâtiment |
| prestataire_id | FK Prestataire | Prestataire titulaire du contrat |
| type_equipement | enum | `TypeEquipement` (`api/app/models/prestataires.py`) — la liste des valeurs vit là et nulle part ailleurs ; les libellés de l'écran dans `front/src/lib/prestataires.ts` |
| libelle | string | Intitulé lisible ex. « Ascenseur bât. 1 », « Chaudière bât. 2-3 » |
| numero_contrat | string | Numéro de référence du contrat |
| date_debut | date | Date d'entrée en vigueur |
| date_fin | date | Nullable — contrat à durée indéterminée si null |
| prochaine_visite | date | Nullable — date de la prochaine intervention planifiée |
| actif | boolean | Contrat toujours en vigueur |
| notes | text | Nullable — consignes d'accès, horaires prestataire, etc. |
### ConfigSauvegarde  *(paramètres de la sauvegarde périodique)*

> Une seule ligne dans la base (configuration globale). Gérée par l'admin uniquement (EF-WEB-015). La sauvegarde produit un export horodaté de la base + les fichiers uploadés (documents, pièces jointes).

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | Toujours 1 (ligne unique) |
| active | boolean | Active ou désactive le cron automatique |
| frequence | enum | `quotidienne` \| `hebdomadaire` \| `mensuelle` — défaut : `hebdomadaire` |
| heure_execution | time | Heure de déclenchement (ex. `03:00`) |
| jour_semaine | integer | 0 = lundi … 6 = dimanche — significatif si fréquence = `hebdomadaire` |
| jour_mois | integer | 1–28 — significatif si fréquence = `mensuelle` |
| nb_versions_conservees | integer | Nombre de sauvegardes historisées avant rotation — défaut : 3, min : 1, max : 30 |
| modifie_par_id | FK Utilisateur | Nullable — dernier admin ayant sauvegardé |
| modifie_le | datetime | Nullable |

### HistoriqueSauvegarde  *(journal des sauvegardes effectuées)*

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| declenchee_par | enum | `automatique` \| `manuelle` |
| declenchee_par_user_id | FK Utilisateur | Nullable — null si automatique |
| statut | enum | `en_cours` \| `reussie` \| `echouee` |
| fichier_nom | string | Ex. `sauvegarde_2026-02-28_0300.tar.gz` |
| fichier_chemin | string | Chemin local dans le volume (`/backups/…`) |
| taille_octets | integer | Nullable — renseigné à la fin de l'opération |
| message_erreur | text | Nullable — détail en cas d'échec |
| cree_le | datetime | Début de l'opération |
| terminee_le | datetime | Nullable — fin de l'opération |

---
### ModèleEmail  *(templates d’emails paramétrables)*

> Chaque événement déclencheur est associé à un template Jinja2 éditable par l’admin. Le rendu est effectué côté API au moment de l’envoi. Les templates système (réinitialisation MDP, invitation) sont modifiables en contenu mais pas désactivables.

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| code | string UNIQUE | Identifiant stable de l’événement (voir catalogue ci-dessous) |
| libelle | string | Libellé affiché dans l’interface admin |
| sujet | string | Objet de l’email — syntaxe Jinja2, ex. `[Résidence] Ticket n°{{ ticket.numero }} mis à jour` |
| corps_html | text | Corps HTML du mail — syntaxe Jinja2 |
| corps_texte | text | Version texte brut (fallback) — syntaxe Jinja2 |
| variables_disponibles | JSON | Documentation des variables injectées (générée par l’API, en lecture seule dans l’UI) |
| desactivable | boolean | `false` pour les templates système (MDP, invitation) |
| actif | boolean | Si `false`, l’email n’est pas envoyé pour cet événement |
| modifie_par_id | FK Utilisateur | Nullable — dernier admin ayant sauvegardé |
| modifie_le | datetime | Nullable |

**Catalogue des événements :**

| code | Déclencheur | Destinataires | Système ? |
|------|-------------|---------------|-----------|
| `invitation_resident` | Lien d’invitation envoyé | Nouvel utilisateur invité | oui |
| `reinitialisation_mdp` | Demande de réinit MDP | Utilisateur demandé | oui |
| `compte_en_attente` | Inscription non reconnue | CS | non |
| `compte_active` | Compte validé par CS | Résident | non |
| `compte_refuse` | Compte refusé par CS | Résident | non |
| `locataire_validation_demande` | Locataire s’inscrit sur un lot | Copropriétaire bailleur | non |
| `locataire_valide` | Bailleur valide le locataire | Locataire | non |
| `locataire_refuse` | Bailleur refuse le locataire | Locataire | non |
| `ticket_cree_cs` | Nouveau ticket soumis | CS (+ syndic si urgence). E-mail syndic : photos en PJ, CC = utilisateurs avec rôle `conseil_syndical` | non |
| `ticket_statut_change` | Statut d’un ticket modifié | Auteur du ticket | non |
| `ticket_urgence_bailleur` | Ticket urgence d’un locataire | Bailleur + mandataire du lot | non |
| `vigik_commande_recue` | Demande de vigik soumise | CS | non |
| `vigik_accepte` | Demande de vigik acceptée | Demandeur | non |
| `vigik_refuse` | Demande de vigik refusée | Demandeur | non |
| `calendrier_evenement_cree` | Nouvel événement calendrier | Résidents du périmètre | non |
| `document_publie` | Nouveau document déposé | Ayants droit selon profil | non |
| `digest_quotidien` | Cron 18 h (si opt-in) | Utilisateur abonné | non |
| `digest_hebdomadaire` | Cron lundi 9 h (si opt-in) | Utilisateur abonné | non |
| `sauvegarde_echec` | Échec d'une sauvegarde automatique | Admin | oui |

**Variables communes injectées dans tous les templates :**

```
{{ residence.nom }}         — « Résidence du Parc »
{{ residence.adresse }}     — adresse complète
{{ destinataire.prenom }}   — prénom du destinataire
{{ destinataire.nom }}
{{ app.url }}               — URL de base de l’application
{{ annee }}                 — année en cours (pied de page)
```

*Variables spécifiques* (ex. `{{ ticket.numero }}`, `{{ ticket.titre }}`, `{{ vigik.code }}`, `{{ evenement.titre }}`) sont documentées dans `variables_disponibles` de chaque template.

---

### ProfilAccèsDocument  *(templates nommés de droits d'accès)*

> Détermine quels statuts/rôles peuvent lire un document. Chaque profil est un template réutilisable assigné à une catégorie de document (ou en surcharge sur un document individuel). Les profils sont **configurables par l'admin** sans modifier le code.

| Champ | Type | Description |
|-------|------|---------|
| id | integer PK | — |
| code | string UNIQUE | Identifiant lisible : `résidence_tous`, `copropriétaires_et_cs`, `cs_syndic_uniquement`, `lot_occupants`, `lot_propriétaires` |
| libelle | string | Libellé affiché dans l'interface |
| description | string | Description des personas couverts |
| roles_autorises | JSON array | Liste de valeurs `statut` autorisées : ex. `["copropriétaire_résident", "copropriétaire_bailleur", "locataire", "mandataire", "syndic"]` |
| require_cs | boolean | Si `true`, les membres `conseil_syndical` voient toujours ce document (en plus des statuts listés) |
| actif | boolean | Peut être désactivé sans suppression |

**Profils préconfigurés :**

| code | Qui peut lire |
|------|---------------|
| `résidence_tous` | Tous les résidents actifs (copropriétaire résident, bailleur, locataire, mandataire) + syndic + CS |
| `copropriétaires_et_cs` | Copropriétaires seulement (résidents + bailleurs) + CS + syndic — **exclut locataires et mandataires** |
| `cs_syndic_uniquement` | Conseil syndical + syndic + admin uniquement |
| `lot_occupants` | Propriétaire(s) du lot + locataire actif du lot + mandataire du lot + CS + syndic |
| `lot_propriétaires` | Propriétaire(s) du lot + mandataire du lot + CS + syndic — **exclut le locataire** |

---

### CatégorieDocument  *(catalogue des types de documents)*

> Remplace l'enum `type` de l'ancienne entité `Document`. Chaque catégorie définit un profil d'accès par défaut et un périmètre par défaut. L'admin peut créer de nouvelles catégories sans redéploiement.

| Champ | Type | Description |
|-------|------|---------|
| id | integer PK | — |
| code | string UNIQUE | Identifiant stable : ex. `contrat_fournisseur`, `pv_ag`, `diagnostic` |
| libelle | string | Libellé affiché |
| profil_acces_id | FK ProfilAccèsDocument | Profil d'accès appliqué par défaut |
| perimetre_defaut | enum | `résidence` \| `bâtiment` \| `lot` |
| surcharge_autorisee | boolean | Si `false`, le profil ne peut pas être modifié au niveau du document individuel |
| actif | boolean | Catégorie disponible au dépôt |

**Catalogue initial :**

| code | Libellé | Profil par défaut | Périmètre défaut | Surcharge |
|------|---------|-------------------|------------------|-----------|
| `reglement_copropriete` | Règlement de copropriété | `résidence_tous` | résidence | non |
| `pv_ag` | PV d'Assemblée Générale | `résidence_tous` | résidence | non |
| `fiche_synthetique` | Fiche synthétique annuelle | `résidence_tous` | résidence | non |
| `plan_residence` | Plan de la résidence | `résidence_tous` | résidence | non |
| `attestation_lot` | Attestation (lot) | `lot_occupants` | lot | oui |
| `diagnostic_lot` | Diagnostic (lot) | `lot_occupants` | lot | oui |
| `contrat_fournisseur` | Contrat fournisseur | `copropriétaires_et_cs` | résidence | oui |
| `contrat_assurance` | Contrat assurance | `copropriétaires_et_cs` | résidence | oui |
| `budget_comptes` | Budget / Comptes annuels | `copropriétaires_et_cs` | résidence | non |
| `devis_travaux` | Devis travaux | `cs_syndic_uniquement` | bâtiment | oui |
| `document_interne_cs` | Document interne CS | `cs_syndic_uniquement` | résidence | non |

---

### Document

> L'accès effectif est calculé ainsi : `profil_acces_override_id ?? categorie.profil_acces_id`. Le périmètre (résidence / bâtiment / lot) s'applique en filtre supplémentaire.

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| categorie_id | FK CatégorieDocument | Remplace l'ancien enum `type` |
| titre | string | — |
| fichier_url | string | Chemin vers le fichier |
| perimetre | enum | `résidence` \| `bâtiment` \| `lot` |
| batiment_id | FK Bâtiment | Nullable — si périmètre = bâtiment |
| lot_id | FK Lot | Nullable — si périmètre = lot |
| profil_acces_override_id | FK ProfilAccèsDocument | Nullable — surcharge du profil de la catégorie (si `categorie.surcharge_autorisee = true`) |
| publie_par_id | FK Utilisateur | Auteur de l'upload (CS ou admin) |
| publie_le | datetime | — |

---

### Evenement  *(calendrier de la résidence)*

> Événements planifiés de la résidence : travaux, coupures, AG, interventions prestataires, maintenances récurrentes. Affiché dans trois vues (Liste, Kanban, Archives). Les prestations ponctuelles issues du module Prestataires apparaissent aussi dans le calendrier.

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| titre | string | — |
| description | text | Nullable |
| type | enum | `travaux` \| `coupure` \| `ag` \| `maintenance` \| `maintenance_recurrente` \| `autre` |
| lieu | string | Nullable |
| debut | datetime | Date/heure de début |
| fin | datetime | Nullable — date/heure de fin |
| perimetre | string | `résidence` \| `bâtiment` |
| batiment_id | FK Bâtiment | Nullable — si périmètre = bâtiment |
| auteur_id | FK Utilisateur | Créateur de l'événement |
| statut_kanban | enum | Nullable — `ag` \| `cs` \| `syndic` \| `fournisseur` \| `termine` \| `annule` |
| prestataire_id | FK Prestataire | Nullable — prestataire associé |
| frequence_type | string | Nullable — `semaines` \| `mois` \| `fois_par_an` |
| frequence_valeur | integer | Nullable — valeur de la fréquence de récurrence |
| affichable | boolean | Visible dans le dashboard (événements récents) — défaut : `false` |
| archivee | boolean | Archivé (ne plus afficher dans la vue courante) |
| cree_le | datetime | — |
| mis_a_jour_le | datetime | Nullable |

### LocationBail  *(contrat locatif — gestion locative bailleur)*

> Lie un copropriétaire bailleur, un locataire (compte enregistré ou coordonnées libres) et un ou plusieurs lots. Le bailleur crée un bail sur un ou plusieurs lots par `POST /bailleur/baux/creer-multi` — **une seule route**, y compris pour un lot unique : la variante `POST /bailleur/lots/{lot_id}/bail` en était une copie et a été retirée le 12/09/2026 (#932). À la terminaison du bail, les accès (vigiks/TC) sont automatiquement marqués rendus.

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| lot_id | FK Lot | Lot concerné par le bail |
| bailleur_id | FK Utilisateur | Copropriétaire bailleur |
| locataire_id | FK Utilisateur | Nullable — compte enregistré du locataire |
| locataire_nom | string | Nullable — si pas de compte : nom saisi manuellement |
| locataire_prenom | string | Nullable — prénom saisi manuellement |
| locataire_email | string | Nullable — email saisi manuellement |
| locataire_telephone | string | Nullable — téléphone saisi manuellement |
| date_entree | date | Date d'entrée dans les lieux |
| date_sortie_prevue | date | Nullable — date de sortie prévue |
| date_sortie_reelle | date | Nullable — date de sortie effective |
| statut | enum | `actif` \| `termine` \| `en_cours_sortie` |
| notes | text | Nullable |
| cree_le | datetime | — |
| mis_a_jour_le | datetime | — |

### RemiseObjet  *(objet physique remis au locataire)*

> Suivi des objets physiques (clés, télécommandes, vigiks) remis au locataire dans le cadre d'un bail. Permet le contrôle au départ du locataire.

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| bail_id | FK LocationBail | Bail associé |
| type | enum | `cle` \| `telecommande` \| `vigik` \| `autre` |
| libelle | string | Ex. « Clé Porte palière », « Télécommande Parking » |
| quantite | integer | Nombre d'exemplaires (défaut : 1) |
| reference | string | Nullable — ex. « TC-042 », « VGK-007 » |
| statut | enum | `en_possession` \| `rendu` \| `perdu` \| `non_remis` |
| remis_le | date | Nullable — date de remise |
| rendu_le | date | Nullable — date de restitution |
| notes | text | Nullable |
| cree_le | datetime | — |

### PetiteAnnonce  *(petites annonces — Communauté)*

> Troisième onglet de la section Communauté (après Sondages et Boîte à idées). Permet aux résidents de publier des annonces de vente, don ou recherche avec photos (max 5).

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| titre | string | — |
| description | text | Contenu HTML riche |
| type_annonce | enum | `vente` \| `don` \| `recherche` |
| categorie | enum | `appartement` \| `parking_cave` \| `mobilier` \| `electromenager` \| `high_tech` \| `vehicule` \| `vetements` \| `services` \| `divers` |
| prix | decimal | Nullable — montant (si vente) |
| negotiable | boolean | Prix négociable (défaut : `false`) |
| photos_json | string | JSON array d'URLs (max 5 photos) |
| statut | enum | `disponible` \| `reserve` \| `vendu` \| `archive` |
| contact_visible | boolean | Autoriser l'affichage email/prénom-nom (défaut : `true`) |
| auteur_id | FK Utilisateur | Auteur de l'annonce |
| cree_le | datetime | — |
| mis_a_jour_le | datetime | Nullable |

---

## Relations principales

```
Copropriété ─< Bâtiment ─< Lot
Lot >─< Utilisateur  (via UserLot)
Lot ─< Vigik
Lot ─< Télécommande
Lot ─< LocationBail ─< RemiseObjet
Utilisateur ─< Ticket ─< MessageTicket
Utilisateur ─< CommandeAccès
Utilisateur ─< Publication ─< Sondage ─< OptionSondage >─< VoteSondage
Utilisateur ─< PetiteAnnonce
Utilisateur (bailleur) ─< LocationBail
Utilisateur (locataire) ─<? LocationBail  (optionnel, sinon coordonnées libres)
Prestataire ─< MissionPrestataire ─< ContratEntretien ─> Copropriété / Bâtiment
Prestataire ─<? Evenement  (liaison optionnelle)
Evenement ─> Bâtiment  (périmètre optionnel)
ModèleEmail  (1 entrée par code d'événement, éditable par admin)
ProfilAccèsDocument ─< CatégorieDocument ─< Document
Document >─ ProfilAccèsDocument  (override optionnel)
Bâtiment / Lot ─< Document
Mandataire (Utilisateur) ─< Mandat ─> Bailleur (Utilisateur)
Mandat ─> Lot
AgCsInfo  (ligne unique — AG d'élection du CS)
MembreCS ─> Bâtiment  (localisation)
MembreCS ─> Utilisateur  (photo de profil, optionnel)
SyndicInfo  (ligne unique — cabinet syndic)
MembreSyndic ─> Utilisateur  (photo de profil, optionnel)
ConfigSite  (clé/valeur — configuration UI + contenus légaux, admin)
```

---

### AgCsInfo  *(informations AG du Conseil Syndical)*

> Un seul enregistrement (upsert). Mémorise l'année et la date exacte de l'AG lors de laquelle le Conseil Syndical a été élu. Affiché dans l'annuaire public.

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | Toujours 1 (ligne unique) |
| ag_annee | integer | Année de l'AG d'élection (ex. 2025) |
| ag_date | date | Date précise de l'AG (ex. 12 juin 2025) |

### MembreCS  *(membres du Conseil Syndical)*

> Entité indépendante des comptes `Utilisateur`. Un membre CS peut éventuellement être lié à un compte via `user_id` (optionnel), ce qui permet l'affichage de la photo de profil dans l'annuaire.

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| genre | enum | `Mr` \| `Mme` \| `Mlle` |
| prenom | string | — |
| nom | string | — |
| batiment_id | FK Bâtiment | Bâtiment de résidence (issu de l'import des lots) |
| etage | integer | Étage de résidence (issu de l'import des lots) |
| ordre | integer | Ordre d'affichage (défaut : 0) |
| user_id | FK Utilisateur | Nullable — lien vers le compte utilisateur (pour la photo de profil) |

### SyndicInfo  *(informations du syndic)*

> Un seul enregistrement (upsert). Raison sociale et adresse du cabinet syndic.

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | Toujours 1 (ligne unique) |
| nom_syndic | string | Raison sociale du cabinet syndic |
| adresse | string | Adresse du cabinet |

### MembreSyndic  *(contacts du syndic)*

> Contacts individuels au sein du cabinet syndic. Comme pour `MembreCS`, l'entité est indépendante des comptes `Utilisateur`.

| Champ | Type | Description |
|-------|------|-------------|
| id | integer PK | — |
| genre | enum | `Mr` \| `Mme` \| `Mlle` |
| prenom | string | — |
| nom | string | — |
| fonction | string | Nullable — poste dans le cabinet |
| email | string | Nullable |
| telephone | string | Nullable — CSV si plusieurs numéros (ex. `01 23 45 67 89,06 12 34 56 78`) |
| est_principal | boolean | Marque l'interlocuteur principal (badge doré dans l'annuaire) |
| ordre | integer | Ordre d'affichage |
| user_id | FK Utilisateur | Nullable — lien vers le compte utilisateur (pour la photo de profil) |

---

### ConfigSite  *(paramètres de configuration persistants)*

> Table clé/valeur permettant à l'admin de personnaliser l'application depuis l'interface sans redéploiement. Stockée en base pour être cohérente sur tous les appareils. Deux sous-ensembles logiques :
> - **Configuration UI** : `site_nom`, `site_description`, et pour chaque page : `page.[cle].titre`, `page.[cle].icone`, `page.[cle].descriptif` (sous-titre HTML riche affiché sous le titre de chaque page).
> - **Contenus légaux** : `mentions_legales`, `politique_confidentialite` (HTML riche, éditables via l'éditeur TipTap de l'interface admin, rendus publiquement sans authentification).

| Champ | Type | Description |
|-------|------|-------------|
| cle | string PK | Identifiant de la clé (ex. `site_nom`, `page.annuaire.descriptif`) |
| valeur | string | Valeur textuelle ou HTML |

**Clés de configuration UI prédéfinies :**

| Clé | Usage |
|-----|-------|
| `site_nom` | Nom de la résidence affiché dans les titres et emails |
| `page.[route].titre` | Titre de la page (ex. `page.annuaire.titre`) |
| `page.[route].icone` | Nom d'icône Lucide (ex. `page.annuaire.icone`) |
| `page.[route].descriptif` | Sous-titre HTML riche affiché sous le `<h1>` de la page |
| `mentions_legales` | Contenu HTML de la page Mentions légales |
| `politique_confidentialite` | Contenu HTML de la page Politique de confidentialité |

- Un `locataire` ou `mandataire` ne peut avoir `role = conseil_syndical` ou `role = admin`.
- **Accès aux documents — algorithme de résolution :**
  1. `profil = document.profil_acces_override_id ?? document.categorie.profil_acces_id`
  2. `statut_utilisateur IN profil.roles_autorises` → autorisé si vrai
  3. Si `profil.require_cs = true` ET `utilisateur.role = conseil_syndical` → toujours autorisé
  4. Filtre périmètre : si `document.perimetre = bâtiment` → vérifier que `utilisateur.batiment_id = document.batiment_id` ; si `document.perimetre = lot` → vérifier que `UserLot(user_id, lot_id)` existe
  5. L'admin voit tous les documents sans restriction de profil.
- `Document.profil_acces_override_id` ne peut être renseigné que par un utilisateur avec `role = admin`, et uniquement si `categorie.surcharge_autorisee = true`. Le CS ne peut pas modifier le profil d'accès lors de l'upload.
- Un `syndic` a `role = résident` (lecture seule) — il n'a pas de droits d'écriture applicatifs.
- `UserLot` : un lot peut avoir plusieurs entrées `type_lien = propriétaire` (co-propriété, ex. couple).
- `UserLot` : un locataire (`type_lien = locataire`) ne peut être lié qu'à un lot dont au moins un propriétaire est `copropriétaire_bailleur`.
- `VoteSondage` : unicité `(sondage_id, user_id)` — un vote par utilisateur par sondage.
- `Mandat` : unicité `(mandataire_id, lot_id)` — un mandataire actif par lot.
- Lorsqu'un locataire crée un ticket, le système notifie : tous les propriétaires du lot (UserLot `type_lien = propriétaire`) **et** les mandataires actifs du lot (`Mandat.date_fin IS NULL OR date_fin >= aujourd'hui`).
