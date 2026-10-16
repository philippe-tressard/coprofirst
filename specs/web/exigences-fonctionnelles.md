# Exigences fonctionnelles — Site web

> Priorités : **Haute** (MVP), **Moyenne** (phase 1), **Basse** (phase 2).

---

## Authentification & comptes

### EF-WEB-001 — Création de compte résident
- **Priorité :** Haute
- **Description :** Un utilisateur peut créer un compte en saisissant nom, prénom, email, téléphone, mot de passe (ou OAuth Apple/Google), bâtiment et statut. Voir CU-001 pour les règles détaillées.
- **Critères d'acceptance :**
  - Un locataire ne peut pas sélectionner le rôle `conseil_syndical` ni `admin`.
  - Un mandataire ne peut pas sélectionner `conseil_syndical` ni `admin`.
  - Le compte est activé automatiquement si le nom figure dans la liste importée, sinon mis en attente.
  - Le champ **NOM est automatiquement converti en majuscules** lors de la saisie (transformation visuelle en temps réel + valeur stockée en majuscules).
  - Les champs obligatoires sont clairement signalés (*) ; les facultatifs sont explicitement indiqués comme tels (Art. 13.2.e RGPD).
  - Un lien vers la **politique de confidentialité** est affiché sur le formulaire avant la soumission (Art. 13 RGPD).
  - Une **case à cocher non pré-cochée** « J'ai lu et j'accepte la politique de confidentialité » est obligatoire pour valider le formulaire (Art. 7 RGPD — consentement libre, éclairé, univoque).
  - Une **case à cocher séparée, non pré-cochée** et optionnelle permet d'accepter les communications d'actualités (consentement distinct par finalité, Art. 7 RGPD).
  - Un encadré résumé indique : responsable de traitement (syndicat des copropriétaires), finalité (gestion de la copropriété), durée de conservation, droits de la personne et contact CNIL.
  - Un utilisateur déclarant avoir moins de **15 ans** est bloqué à l'inscription (Art. 8 RGPD + Loi n° 2018-493 du 20 juin 2018).

### EF-WEB-002 — Connexion
- **Priorité :** Haute
- **Description :** Connexion par email/mot de passe ou via OAuth (Apple, Google). Session via JWT (access 15 min + refresh 7 j) stockés en cookies HttpOnly.
- **Critères d’acceptance :**
  - Après 5 tentatives échouées : blocage temporaire 15 min.
  - Déconnexion possible depuis n'importe quelle page.

### EF-WEB-003 — Récupération de mot de passe
- **Priorité :** Haute
- **Description :** Envoi d’un lien de réinitialisation par email, valide 1 heure.
### EF-WEB-004 — Onboarding progressif à la première connexion
- **Priorité :** Moyenne
- **Description :** À la première connexion d'un nouvel utilisateur, l'application déclenche un assistant d'accueil non bloquant. Voir CU-005 pour le détail du parcours.
- **Critères d'acceptance :**
  - L'assistant comporte 4 étapes séquentielles, chacune skippable individuellement.
  - La progression est persistée côté serveur (l'assistant n'est pas relancé si l'utilisateur quitte avant de terminer ; il reprend à l'étape suivante à la connexion suivante).
  - L'assistant peut être relancé manuellement depuis Paramètres > Mon profil > Revoir le guide.
  - Une barre de complétion de profil (%) reste affichée dans l'encart du tableau de bord jusqu'à 100 % de complétion.
  - Les téléphones vides (aucun ticket, aucune actualité) affichent un CTA contextuel : « Signaler un problème », « Consulter les actualités » (empty state actif).
  - L'assistant ne se déclenche pas pour les comptes importés/migrés ayant déjà un profil complet (heuristique : nom, lot, email renseignés).

### EF-WEB-005 — Tableau de bord (Accueil)
- **Priorité :** Haute
- **Description :** La page d'accueil après connexion affiche un tableau de bord personnalisé selon le rôle et le bâtiment de l'utilisateur. Elle agrège en temps réel les KPIs, alertes urgentes, prochaines échéances et un fil d'activité chronologique.
- **Critères d'acceptance :**
  - **Hero** : affiche le nom de l'utilisateur, son lot et son rôle.
  - **Consignes de la copropriété** : lien proéminent vers la page résidence, mis en avant visuellement pour les locataires et les nouveaux arrivants (animation pulsante ambre).
  - **KPIs** : tickets ouverts, événements à venir, résolution moyenne (30 derniers jours), publications récentes. Chaque KPI est cliquable vers la page correspondante.
  - **Alertes urgentes** : les publications urgentes actives sont affichées en tête avec un fieldset rouge, une barre de progression temporelle et l'indication du périmètre concerné.
  - **Prochaines échéances** : événements futurs et contrats/assurances à échéance, triés par date. Chaque item est expandable au clic pour afficher lieu, périmètre, prestataire, dates, description et lien vers la page complète. Filtrage par rôle (les locataires ne voient pas les items AG) et par périmètre (bâtiment de l'utilisateur).
  - **Fil d'activité** : timeline chronologique des 377 derniers jours regroupée par jour.
    - Distinction visuelle par type (couleur du bord gauche + chip type) : tickets (bleu), publications (vert), événements (ambre), sondages (violet), devis (émeraude).
    - Badge « NEW » pulsant pour les items créés il y a moins de 48 heures.
    - Items récents (< 30 jours) affichés par défaut ; items anciens (30-377 jours) dans un accordéon replié.
    - Les tickets non résolus et événements non réalisés restent toujours dans la section récente.
    - Les événements avec date future apparaissent uniquement dans Prochaines échéances (dédupliqués du fil).
    - Chaque item est expandable au clic pour voir le détail complet (description, image, métadonnées, lien).
    - Un seul item peut être ouvert à la fois, partagé entre prochaines échéances et fil d'activité.
  - **Filtrage rôle/périmètre** : un locataire ne voit pas les items liés à la catégorie AG. Le périmètre de l'utilisateur (bâtiment) est respecté. Les périmètres universels (résidence, parking, cave, AFUL) sont visibles par tous.
  - **Raccourcis rapides** : pilules de navigation vers les pages principales avec compteurs.

---

## Espace copropriétaire

### EF-WEB-010 — Consultation de son lot
- **Priorité :** Haute
- **Description :** Un résident consulte les caractéristiques de son lot (type, étage, superficie) et l’historique des interventions.
- **Critères d’acceptance :**
  - Un résident ne voit que ses propres lots.
  - Le syndic voit tous les lots en lecture seule.

### EF-WEB-011 — Gestion des vigiks et télécommandes
- **Priorité :** Haute
- **Description :** Un résident consulte ses vigiks et télécommandes actifs et peut soumettre une commande.
- **Critères d’acceptance :**
  - La demande est transmise au conseil syndical pour traitement.
  - Un email de confirmation est envoyé au demandeur à chaque changement de statut.
  - Dans la FAQ, la question relative au prix des badges est adressable en lien profond `/faq#badge-prix` et affiche un lien d'action direct vers `Accès & badges` (ancre `Nouvelle demande`) pour accélérer la création de demande.

### ~~EF-WEB-012 — Accès aux documents~~ *(supprimé — la bibliothèque documentaire publique a été retirée du menu résident. Les documents restent gérés en interne par le CS/admin, via les contrats d'entretien.)*

### ~~EF-WEB-013 — Administration du catalogue de catégories et des profils d'accès~~ *(supprimé — fonctionnalité retirée du parcours résident. Upload de documents accessible uniquement depuis Prestataires pour les CS/admin.)*

### EF-WEB-014 — Configuration de la fiche copropriété
- **Priorité :** Moyenne
- **Description :** **L'admin** peut compléter et mettre à jour la fiche technique de la copropriété (informations légales, assurance, carnet d'entretien). Les résidents et le syndic accèdent à ces informations en **lecture seule** depuis la section « État de la résidence ».
- **Critères d'acceptance :**
  - **[Admin] Informations générales** : nom, adresse, année de construction, nombre total de lots, numéro d'immatriculation au registre national des copropriétés (ANAH — champ obligatoire selon ALUR).
  - **[Admin] Assurance immeuble** : compagnie, numéro de police, date d'échéance. Un indicateur visuel avertit l'admin si la date d'échéance est dans les 60 jours.
  - **[Admin] Contrats d'entretien** (carnet d'entretien — Art. L. 731-2 CCH) : l'admin peut créer, modifier ou archiver un contrat en renseignant : type d'équipement (ascenseur, chauffage collectif, VMC, porte de parking, extincteurs, interphone/digicode, espaces verts, nettoyage, autre), libellé, prestataire (liste déroulante `Prestataire`), numéro de contrat, date de début, date de fin (optionnelle), date de la prochaine visite (optionnelle), notes (consignes d'accès, horaires).
  - Un contrat peut être lié à l'ensemble de la résidence ou à un bâtiment spécifique.
  - La liste des contrats actifs est accessible en **lecture** à tous les résidents depuis « Services pratiques > Prestataires » avec le nom du prestataire, le type d'équipement et les notes publiques (pas le numéro de contrat, ni les montants).
  - Le syndic accède à la fiche complète (y compris numéros de contrat) en lecture seule.
  - Les champs `numero_immatriculation` et `assurance_echeance` sont mis en évidence dans la vue publique (obligation légale et protection des résidents).

### EF-WEB-015 — Sauvegardes périodiques et restauration
- **Priorité :** Haute
- **Description :** **L'admin** configure un système de sauvegarde automatique de la base de données et des fichiers uploadés (documents, pièces jointes tickets). Les sauvegardes sont conservées localement avec rotation automatique selon un historique paramétrable.
- **Critères d'acceptance :**
  - **[Admin] Configuration** : l'admin peut définir :
    - Fréquence : `quotidienne` / `hebdomadaire` (défaut) / `mensuelle`.
    - Heure de déclenchement (défaut : 03 h 00, hors pics d'utilisation).
    - Jour de la semaine (si hebdomadaire, défaut : dimanche) ou jour du mois (si mensuelle).
    - Nombre de versions historisées avant rotation : entre 1 et 30 (défaut : 3). Au-delà, la plus ancienne est supprimée automatiquement.
  - **[Admin] Déclenchement manuel** : un bouton « Sauvegarder maintenant » lance immédiatement une sauvegarde hors-cycle sans modifier le planning automatique.
  - **[Admin] Historique** : liste des sauvegardes triées par date décroissante. Chaque ligne affiche : date/heure, type (automatique / manuelle), statut (✅ réussie / ⚠️ échec), taille du fichier, durée de l'opération.
  - **[Admin] Téléchargement** : chaque sauvegarde réussie est téléchargeable depuis l'interface (archive `.tar.gz`).
  - **[Admin] Restauration** : l'admin peut initier une restauration à partir d'une version historisée. Action précédée d'un avertissement explicite (texte : « Cette action remplace toutes les données actuelles. Cette opération est irréversible. ») et d'une confirmation par saisie de mot de passe admin.
  - **Notification d'échec** : si une sauvegarde automatique échoue, l'admin reçoit un email d'alerte (code `sauvegarde_echec`) et une alerte visible dans le tableau de bord CS au prochain chargement.
  - Le périmètre de la sauvegarde couvre : export vérifié de la base + répertoire des fichiers uploadés. Les templates et logs applicatifs ne font pas partie de la sauvegarde (ils sont dans l'image Docker).
  - Les sauvegardes sont stockées dans le volume Docker dédié (`/backups`) — monté de préférence sur un support distinct du stockage principal (clé USB, NAS).

---

## Demandes & tickets

### EF-WEB-020 — Création d’un ticket
- **Priorité :** Haute
- **Description :** Un résident crée un ticket (panne, nuisance, question, urgence, bug) avec titre, description et pièces jointes optionnelles (photos).
- **Critères d’acceptance :**
  - Un numéro de ticket est attribué et affiché immédiatement.
  - Les tickets `urgence` déclenchent une notification prioritaire au conseil syndical **et au syndic**, indépendamment du rôle lecture seule de ce dernier (les urgences ne sont pas filtrées par les droits d'écriture — cf. EF-WEB-072).
  - Un réglage **Admin → Paramétrage site** permet d'activer l'envoi d'un e-mail au contact administrateur du site **uniquement** pour les tickets de catégorie `bug`.
  - Un second réglage **Admin → Paramétrage site** permet d'envoyer un e-mail au gestionnaire du site dès qu'un nouveau compte utilisateur est créé et placé en attente de validation.
  - Les tickets `urgence` ne déclenchent **pas** cette notification e-mail du site manager ; ils restent traités via le circuit opérationnel CS / syndic.
  - Si l'auteur est un **locataire**, tous les copropriétaires bailleurs du lot concerné **et** le mandataire (s'il en a un) reçoivent une notification à la création du ticket et à chaque changement de statut.
### EF-WEB-021 — Suivi des tickets
- **Priorité :** Haute
- **Description :** Le résident suit le statut de ses tickets et échange des messages avec le conseil syndical.
- **Critères d’acceptance :**
  - Statuts visibles : ouvert / en cours / résolu / annulé / fermé.
  - La barre de filtres propose uniquement **Tous**, **Ouvert** et **En cours**. Les tickets résolus, annulés ou fermés ne figurent plus dans les filtres.
  - Les tickets résolus, annulés ou fermés sont immédiatement déplacés dans une section **Historique** en bas de page, groupés par année en accordéon décroissant (3 ans max). Cette section est visible pour tous les profils (copro, CS, admin) et reste affichée même en l'absence de tickets actifs.
  - Le conseil syndical peut modifier le statut et ajouter des messages.
  - Dans l'espace CS, chaque ticket affiche le prénom / nom et le bâtiment du demandeur pour accélérer la qualification et le traitement.
  - Le syndic peut lire les tickets en lecture seule.

---

## Communication

### EF-WEB-030 — Publication d’actualités
- **Priorité :** Haute
- **Description :** Le conseil syndical publie des actualités (annonces, alertes, travaux) visibles par tous les résidents du périmètre ciblé (résidence ou bâtiment).
- **Critères d’acceptance :**
  - Seuls conseil syndical et admin peuvent publier.
  - Le syndic ne peut que lire les publications.
  - Une publication peut être épinglée (affichage prioritaire).
### EF-WEB-034 — Partage automatique des actualités sur WhatsApp
- **Priorité :** Moyenne
- **Description :** Lors de la création d'une publication, le CS peut cocher une option pour que le message soit automatiquement envoyé dans le groupe WhatsApp dédié « 5Hostachy ».
- **Critères d'acceptance :**
  - Un flag optionnel `partager_whatsapp` est disponible dans le formulaire de création de publication (CS uniquement).
  - Si le flag est activé, un message est envoyé automatiquement au groupe WhatsApp après création de la publication via le service `whatsapp-bridge` (Baileys, hébergé en local sur le RPi).
  - Le message inclut le titre et le contenu de la publication.
  - Si une image est attachée à la publication au moment du partage, elle est jointe au message WhatsApp avec le texte en légende.
  - Les publications marquées `urgente` sont précédées d'un préfixe visuel (🚨 URGENT) dans le message WhatsApp.
  - Le partage WhatsApp est activable/désactivable via la configuration serveur (`WHATSAPP_ENABLED`).
  - En cas d'échec de l'envoi WhatsApp, la publication est tout de même créée (pas de rollback) et l'erreur est loguée.
- **Dépendances techniques :**
  - Service Docker `whatsapp-bridge` ajouté au `docker-compose.yml` (Node.js + Baileys + Express).
  - Variables d'environnement : `WHATSAPP_ENABLED`, `WHATSAPP_API_KEY`, `WHATSAPP_API_URL`, `WHATSAPP_GROUP_JID`.
  - Nouveau champ `partager_whatsapp: bool = False` sur le modèle `Publication` (migration Alembic requise).
  - Nouveau utilitaire `api/app/utils/whatsapp.py`.
### EF-WEB-031 — Sondages internes
- **Priorité :** Moyenne
- **Description :** Le conseil syndical crée des sondages (question + options). Les résidents votent (un vote par personne par sondage).
- **Critères d’acceptance :**
  - Les résultats sont visibles après clôture ou en temps réel selon le paramétrage.

### EF-WEB-032 — Boîte à idées
- **Priorité :** Moyenne
- **Description :** Tout résident peut soumettre une idée. Les autres résidents peuvent voter pour prioriser.

### EF-WEB-033 — Calendrier de la résidence
- **Priorité :** Moyenne
- **Description :** Le conseil syndical maintient un calendrier partagé listant les événements planifiés : travaux, coupures d'eau/énergie, AG, interventions prestataires, maintenances.
- **Critères d'acceptance :**
  - Trois vues complémentaires sont disponibles :
    - `Liste` : lecture chronologique des événements et interventions (pilotage quotidien).
    - `Kanban` : suivi d'avancement par statut workflow (CS, syndic, prestataire, terminé, annulé).
    - `Archives` : historique des événements passés et prestations réalisées, regroupé par année/mois.
  - Chaque événement comporte : titre, date/heure de début et de fin, lieu, périmètre (résidence entière ou bâtiment ciblé), description optionnelle, pièce jointe optionnelle.
  - Seuls le conseil syndical et l'admin peuvent créer, modifier ou supprimer un événement.
  - Les prestations ponctuelles acceptées issues du module prestataires apparaissent dans la vue `Liste`.
  - Les prestations ponctuelles issues du module prestataires apparaissent dans la vue `Kanban` dans la colonne correspondant à leur statut (`en_attente`, `accepte`, `realise`, `refuse`).
  - Sur le tableau de bord (Accueil), le bloc `Événements récents` inclut aussi les prestations ponctuelles non terminées (`en_attente`, `accepte`) pour cohérence avec le pilotage calendrier.
  - Les résidents reçoivent une notification à la création d'un événement concernant leur bâtiment (canal configurable : in-app / email / digest).
  - Les événements de type `coupure` et `urgence travaux` déclenchent une notification push immédiate (non différables dans le digest).
  - Un filtre par type d'événement est disponible (travaux, AG, coupure, maintenance, autre).
  - Le calendrier est accessible au syndic en lecture seule.

---

## Accès & sécurité

### EF-WEB-040 — Gestion des badges d’accès
- **Priorité :** Haute
- **Description :** Un résident consulte ses badges actifs et leur statut. Il peut signaler un badge perdu. Le conseil syndical gère les demandes de vigiks et peut les traiter en masse.
- **Critères d'acceptance :**
  - Le conseil syndical peut activer, suspendre ou supprimer un badge.
  - Le conseil syndical voit la liste des demandes de vigiks en attente.
  - **Validation en masse** : un CS peut sélectionner plusieurs demandes (cases à cocher) et les valider ou refuser en une seule action « Valider la sélection (N) » / « Refuser la sélection (N) ».
  - En cas de refus en masse, un motif commun peut être saisi et s'applique à toutes les demandes refusées ; il peut aussi être personnalisé par demande.
  - Chaque demandeur reçoit une notification individuelle du résultat, quelle que soit la modalité de traitement (unitaire ou en masse).
  - La même interface de validation en masse est disponible pour les **comptes en attente de validation** (nouveaux inscrits non reconnus dans la liste des copropriétaires).

---

## Transparence & gouvernance

### EF-WEB-050 — Décisions collectives
- **Priorité :** Moyenne
- **Description :** Le conseil syndical publie les synthèses de votes et résolutions adoptées en AG.
- **Critères d’acceptance :**
  - Visible en lecture par tous les résidents. Le syndic y accède en lecture seule.

---

## Services pratiques

### EF-WEB-060 — Annuaire
- **Priorité :** Moyenne
- **Description :** Annuaire des contacts utiles : membres du Conseil Syndical élu en AG et contacts du cabinet syndic. Pas d'adresses privées de résidents.
- **Critères d'acceptance :**
  - **Section CS** : affiche les membres du CS avec nom, prénom, bâtiment et étage (récupérés de l'import des lots). L'en-tête de section mentionne l'année de l'AG d'élection et la date exacte (ex. « Voté en AG 2025 - 12 juin 2025 »).
  - **Section CS (repères visuels)** : un membre CS peut être marqué « Gestionnaire du Site » (badge immeuble, info-bulle « Gestionnaire du Site »). Un repère optionnel « Président du Conseil Syndical » peut aussi être affiché.
  - **Section Syndic** : affiche la raison sociale et l'adresse du cabinet, puis la liste des contacts avec nom, prénom, fonction, email et téléphone. Le contact principal conserve un repère étoile avec info-bulle « Gestionnaire principal » et une bordure accentée.
  - **Vignette avatar** : chaque carte membre affiche une vignette circulaire. Si le membre est lié à un compte utilisateur possédant une photo de profil, la photo remplace les initiales.
  - **Gestion CS (Espace CS)** : les membres du CS peuvent, depuis leur espace dédié, ajouter, modifier, réordonner et supprimer les membres CS et les contacts syndic. Un membre CS peut être associé à un compte utilisateur existant via recherche par nom/prénom ; le bâtiment et l'étage sont alors auto-remplis depuis l'import des lots. Les indicateurs « Gestionnaire du Site » et « Président » sont éditables dans cette interface.
  - **Gestion Syndic** : les informations du cabinet (raison sociale, adresse) et la liste des contacts sont éditables par les membres CS et l'admin.

### EF-WEB-061 — Prestataires
- **Priorité :** Moyenne
- **Description :** Liste des intervenants autorisés (nom, spécialité, contact, horaires, consignes d’accès).
- **Critères d’acceptance :**
  - Le **conseil syndical et l'admin** peuvent ajouter ou modifier un prestataire. Le syndic ne peut que lire. L'admin peut également associer un prestataire à un contrat d'entretien depuis la fiche copropriété (EF-WEB-014).

### EF-WEB-062 — FAQ et plan de la résidence
- **Priorité :** Moyenne
- **Description :** FAQ statique (règles de vie, déchets, stationnement) et plan interactif de la résidence.

---

## Notifications

### EF-WEB-070 — Notifications in-app
- **Priorité :** Haute
- **Description :** Tout événement important (changement statut ticket, nouvelle actualité, sondage ouvert) génère une notification dans l'interface.
- **Critères d'acceptance :**
  - Depuis Mon profil, l'utilisateur dispose d'une matrice de préférences (lignes = types d'action, colonnes = canaux `dans l'appli` / `par email`) pour affiner précisément ses notifications.
  - Les notifications urgences sont affichées immédiatement, avec un badge visible quel que soit l'écran en cours.
  - L'utilisateur peut activer un **résumé de notifications (digest)** comme alternative aux notifications en temps réel :
    - Fréquence configurable : quotidien (envoi à 18 h) ou hebdomadaire (envoi le lundi à 9 h).
    - Le digest rassemble les tickets mis à jour, les nouvelles actualités, les sondages ouverts et les événements du calendrier de la semaine.
    - Les notifications de catégorie `urgence` ne sont **jamais** différées dans un digest : elles arrivent immédiatement quelle que soit la préférence.
  - Les préférences digest sont accessibles depuis les paramètres > Notifications.
  - Opt-in uniquement : les nouveaux utilisateurs reçoivent les notifications en temps réel par défaut.

### EF-WEB-071 — Notifications push (Web Push API)
- **Priorité :** Basse *(phase 2)*
- **Description :** Envoi de notifications push sur navigateur et mobile (PWA) via Web Push API. L’utilisateur contrôle ses préférences par catégorie (urgences, actualités, tickets).

### EF-WEB-072 — Notifications email
- **Priorité :** Haute
- **Description :** Envoi d’emails transactionnels et informatifs couvrant tous les événements métier (validation de compte, vigik, tickets, calendrier…). Chaque email est rendu depuis un template Jinja2 éditable par l’admin (cf. EF-WEB-073).
- **Critères d’acceptance :**
  - Les événements couverts sont : invitation résident, réinitialisation MDP, compte en attente / validé / refusé, validation locataire (bailleur), statut ticket, ticket urgence, commande vigik (reçue / acceptée / refusée), événement calendrier, digest.
  - L'e-mail syndic (ticket destiné au syndic) inclut les photos en pièces jointes et met en copie (CC) les utilisateurs ayant le rôle `conseil_syndical` (actifs, avec e-mail valide).
  - Chaque email est envoyé uniquement si le template correspondant est actif (`ModèleEmail.actif = true`).
  - Les émails transactionnels liés à la sécurité (`reinitialisation_mdp`, `invitation_resident`) sont toujours envoyés, quelles que soient les préférences de notifications de l’utilisateur.
  - Les emails utilisétés pour des communications non essentielles (actualités, calendrier, digest) incluent un lien de désinscription en un clic (cf. EF-WEB-101).
  - Transport : `fastapi-mail` via SMTP local ou relay (Brevo / Mailgun), configuré par variable d’environnement.

### EF-WEB-073 — Administration des templates d’email
- **Priorité :** Moyenne
- **Description :** L’**admin seul** peut modifier le sujet, le corps HTML et le corps texte de chaque template d’email depuis l’interface. Les templates utilisent la syntaxe Jinja2 avec des variables injectées par l’API.
- **Critères d’acceptance :**
  - L’interface liste tous les templates groupés par domaine (Comptes, Tickets, Vigiks, Calendrier, Digest) avec leur état actif/inactif.
  - Pour chaque template, l’admin dispose : d’un champ « Sujet », d’un éditeur « Corps HTML » (WYSIWYG basique ou mode source), et d’un champ « Corps texte brut » (fallback).
  - Un panneau « Variables disponibles » affiche (en lecture) les variables injectées pour ce template avec leur description, ex. `{{ ticket.numero }}` — *numéro du ticket*.
  - Un bouton « Prévisualiser » rend le template avec des données fictives et affiche l’email tel que le destinataire le recevrait.
  - Un bouton « Envoyer un test » envoie le rendu à l’adresse email de l’admin connecté.
  - Un bouton « Restaurer le défaut » rétablit le contenu livré par défaut (confirmation requise).
  - Les templates marqués `desactivable = false` ne peuvent pas être désactivés (interrupteur grisé avec info-bulle explicative).
  - Toute modification est horodatée et tracte l’admin ayant modifié (`modifie_par_id`, `modifie_le`).
  - Si le template contient une variable inconnue au rendu, l’API log l’erreur et envoie un email d’alerte à l’admin (fail graceful : ne bloque pas l’événement déclencheur).
---

## Conformité RGPD

### EF-WEB-090 — Politique de confidentialité
- **Priorité :** Haute
- **Description :** Une page de politique de confidentialité est accessible depuis le formulaire d'inscription, le pied de page et les paramètres du compte, conformément à l'Art. 13 RGPD (information lors de la collecte directe).
- **Critères d'acceptance :**
  - La page mentionne obligatoirement : identité et coordonnées du responsable de traitement (syndicat des copropriétaires, représenté par le président du conseil syndical), finalités et base légale de chaque traitement (exécution du contrat de copropriété Art. 6.1.b, intérêt légitime Art. 6.1.f, consentement Art. 6.1.a), durées de conservation (compte actif : durée de résidence + 3 ans ; documents de copropriété : 10 ans ; logs techniques : 90 jours), destinataires des données, droits des personnes, droit de réclamation auprès de la **CNIL** (www.cnil.fr).
  - Accessible sans authentification.
  - La date de dernière mise à jour est affichée. En cas de modification impactant les traitements basés sur le consentement, les utilisateurs sont notifiés et doivent re-consentir.
  - Aucun transfert de données hors UE sans mécanisme conforme (clauses contractuelles types CE) — inclut les fournisseurs OAuth Apple et Google.

### EF-WEB-091 — Exercice des droits RGPD depuis l'espace personnel
- **Priorité :** Haute
- **Description :** Tout utilisateur authentifié peut exercer ses droits RGPD directement depuis ses paramètres, sans courrier postal.
- **Critères d'acceptance :**
  - **Droit d'accès (Art. 15)** : export de toutes les données personnelles au format JSON, disponible sous 72 h.
  - **Droit de rectification (Art. 16)** : modification du nom, prénom, email, téléphone depuis le profil.
  - **Droit à l'effacement (Art. 17)** : bouton « Supprimer mon compte » (confirmation en 2 étapes) — supprime les données identifiantes ; les données soumises à obligation légale de conservation sont anonymisées.
  - **Droit à la limitation (Art. 18)** : suspension du compte à la demande de l'utilisateur.
  - **Droit à la portabilité (Art. 20)** : export JSON/CSV des tickets, documents personnels et informations de lot.
  - **Droit d'opposition (Art. 21)** : désactivation des communications non essentielles depuis les préférences de notifications.
  - **Directives post-mortem (Loi Informatique et Libertés, Art. 85)** : champ optionnel permettant d'indiquer la conduite à tenir sur ses données après son décès.
  - Chaque demande est tracée (date, type, statut) ; le responsable de traitement dispose de **30 jours** pour répondre (Art. 12 RGPD).

### EF-WEB-092 — Registre des consentements et des traitements
- **Priorité :** Haute
- **Description :** L'application maintient un registre des consentements recueillis et un registre des activités de traitement (Art. 30 RGPD).
- **Critères d'acceptance :**
  - Chaque consentement est horodaté et associé à la version de la politique de confidentialité en vigueur au moment de la collecte.
  - Le retrait d'un consentement est aussi simple que son accord (Art. 7 §3 RGPD).
  - Aucun cookie non essentiel n'est déposé sans consentement préalable (Directive ePrivacy).
  - Le registre des activités de traitement (Art. 30) est accessible à l'admin et exportable en PDF pour présentation à la CNIL.
  - Les violations de données personnelles sont notifiées à la CNIL dans les **72 heures** (Art. 33 RGPD) et aux personnes concernées si le risque est élevé (Art. 34 RGPD).

---

## Conformité juridique

### EF-WEB-080 — Page « À propos / Licences open source »
- **Priorité :** Moyenne
- **Description :** Une page accessible depuis les paramètres liste l'ensemble des bibliothèques open source utilisées, avec pour chacune : nom, version, auteur/organisation, licence (type + texte complet), lien vers le dépôt source.
- **Critères d'acceptance :**
  - Accessible à tous les utilisateurs authentifiés, en lecture seule.
  - Le contenu est généré automatiquement depuis l'inventaire produit au build (`license-checker` pour le front, `pip-licenses` pour l'API).
  - Les mentions de copyright obligatoires (Apache 2.0 `NOTICE`, MIT copyright header) y figurent intégralement.
  - Les dépendances sous licence GPL/AGPL déclenchent une alerte bloquante dans la pipeline CI.

### EF-WEB-100 — Mentions légales (LCEN Art. 6)
- **Priorité :** Haute
- **Description :** Une page « Mentions légales » est accessible sans authentification depuis le pied de page et le formulaire d'inscription. Elle satisfait aux obligations de l'Art. 6 de la LCEN (Loi n° 2004-575 du 21 juin 2004), qui s'applique à tout service de communication en ligne, y compris les extranets privés.
- **Critères d'acceptance :**
  - La page mentionne obligatoirement : nom et forme juridique de l'éditeur (le syndicat des copropriétaires de la Résidence du Parc), adresse du siège du syndicat, identité du directeur de publication (président du conseil syndical), coordonnées de l'hébergeur (nom, raison sociale, adresse, téléphone — i.e. les coordonnées de la personne hébergeant le Raspberry Pi, ou l'association si applicable).
  - La page est distincte de la politique de confidentialité (les deux peuvent être liées l'une à l'autre).
  - Accessible sans connexion.

### EF-WEB-101 — Conformité anti-spam des emails (LCEN + CPCE Art. L33-4-1)
- **Priorité :** Haute
- **Description :** Tous les emails envoyés par l'application respectent la réglementation française anti-spam.
- **Critères d'acceptance :**
  - Chaque email identifie clairement l'expéditeur : nom de la résidence + adresse email non masquée (pas de `noreply@` sans identité).
  - Les emails d'information non essentielle (actualités, sondages) incluent un **lien de désinscription** fonctionnel en un clic, conduisant à la mise à jour des préférences de notifications.
  - Les emails transactionnels (changement de statut ticket, alerte urgence, validation de compte) sont exemptés du lien de désinscription car liés à l'exécution du contrat.
  - Aucun email n'est envoyé à un utilisateur qui a révoqué son consentement aux communications d'information.
  - Les en-têtes SPF, DKIM et DMARC sont configurés sur le domaine d'envoi (recommandation ANSSI, obligatoire pour la délivrabilité).

### EF-WEB-115 — Configuration des pages (titres, icônes, sous-titres)
- **Priorité :** Moyenne
- **Description :** **L'admin** peut personnaliser depuis l'interface, pour chaque page de l'application, le titre affiché dans le `<h1>`, l'icône Lucide et le sous-titre (descriptif). Les modifications sont persistantes en base (`ConfigSite`) et synchronisées sur tous les appareils.
- **Critères d'acceptance :**
  - Chaque entrée de configuration de page expose : un champ titre (texte court), un champ icône (nom d'icône Lucide), et un éditeur riche (TipTap) pour le sous-titre.
  - Le sous-titre supporte la **mise en forme riche** (gras, italique, listes, liens) et est rendu en HTML sanitarisé (`DOMPurify`) sur chaque page.
  - Les valeurs par défaut (définies dans le code) sont utilisées si aucune personnalisation n'existe en base.
  - La configuration est chargée une seule fois au démarrage de la session et stockée dans un store Svelte réactif (`configStore`) — aucun rechargement de page requis après modification.
  - Accessible uniquement depuis l'onglet **Pages** du panneau d'administration (admin uniquement).

---

## Pilotage & outils conseil syndical

### EF-WEB-110 — Tableau de bord CS (KPIs et alertes)
- **Priorité :** Haute
- **Description :** Les membres du conseil syndical disposent d'un tableau de bord dédié synthétisant l'état opérationnel de la résidence.
- **Critères d'acceptance :**
  - Le tableau affiche en temps réel les indicateurs clés :
    - Nombre de tickets ouverts (total / par catégorie).
    - Tickets sans mise à jour depuis plus de **7 jours** (alerte visuelle en orange).
    - Demandes de vigiks en attente de validation (count + lien direct vers la liste).
    - Comptes résidents en attente d'activation (count + lien).
    - Prochains événements du calendrier de la résidence (3 suivants).
  - Les alertes (>7 j sans mise à jour, >5 vigiks en attente) sont mises en évidence par une couleur distincte et un bandeau en haut du tableau.
  - Le tableau est accessible immédiatement après connexion pour les rôles `conseil_syndical` et `admin`.
  - Un onglet `Tickets` dédié dans l'espace CS permet d'ouvrir chaque ticket, de voir le demandeur, son bâtiment, puis de changer l'état ou commenter sans passer par la vue résident.
  - La maquette visible par les autres rôles ne montre pas ce tableau (pas d'accès partiel).

### EF-WEB-111 — Recherche globale
- **Priorité :** Moyenne
- **Description :** Une barre de recherche globale permet de trouver en une seule requête des tickets, documents, actualités et contacts.
- **Critères d'acceptance :**
  - Accessible depuis un champ persistant dans la barre de navigation principale.
  - La recherche porte sur : titre et description de tickets, nom de fichiers de documents, titre et corps des actualités, noms dans l'annuaire.
  - Les résultats sont regroupés par type (Tickets / Documents / Actualités / Contacts) avec un count par catégorie.
  - La recherche respecte le périmètre de l'utilisateur : un résident ne voit que ses propres tickets et les documents qui lui sont accessibles.
  - Délai de réponse < 300 ms pour les corpus courants (< 10 000 documents).
  - Une recherche vide ou une touche Echap ferme le panneau de résultats.

### EF-WEB-112 — Export par lot (pour vente ou fin de mandat)
- **Priorité :** Moyenne
- **Description :** Un copropriétaire ou un mandataire peut exporter en une seule archive tous les données relatives à son lot (historique de tickets, documents, vigiks, charges).
- **Critères d'acceptance :**
  - Export disponible depuis Espace copropriétaire > Mon lot > Exporter.
  - Formats disponibles : archive ZIP contenant PDF (documents) + JSON (tickets, historique, vigiks).
  - Le périmètre exporté couvre l'intégralité de la durée d'occupation (pas de limite temporelle par défaut).
  - Une option de filtre par période est disponible (ex. « Cette année », « Plage personnalisée »).
  - L'export est généré de façon asynchrone ; l'utilisateur reçoit une notification (in-app + email) avec un lien de téléchargement valable 72 h.
  - L'export est tracé dans le registre des activités (Art. 30 RGPD / portabilité Art. 20).

### EF-WEB-113 — Export et rapports syndic
- **Priorité :** Moyenne
- **Description :** Le syndic (rôle lecture seule) peut générer des rapports structurés sur l'activité de la résidence depuis son tableau de bord dédié.
- **Critères d'acceptance :**
  - Types de rapports disponibles :
    - **Rapport tickets** : liste des tickets sur une période (colonnes : n°, catégorie, statut, date ouverture, date clôture, bâtiment, lot, durée de traitement).
    - **Liste des lots** : tous les lots avec statut, copropriétaire, locataire actif, vigiks actifs.
    - **PV et résolutions AG** : liste des PV disponibles avec liens de téléchargement.
  - Sélecteur de période pour les rapports tickets (prédéfinis : mois courant, trimestre, année ; ou plage libre).
  - Formats d'export : PDF (mise en page propre pour impression) et XLSX (données brutes).
  - L'export ne déclenche pas de notification aux résidents (opération silencieuse).
  - Les rapports sont accessibles depuis un onglet « Rapports » dans l'espace syndic.

### EF-WEB-114 — Statistiques opérationnelles CS
- **Priorité :** Basse *(phase 2)*
- **Description :** Le conseil syndical accède à des statistiques d'activité permettant de piloter la qualité de service.
- **Critères d'acceptance :**
  - Indicateurs disponibles :
    - Délai moyen de prise en charge des tickets (ouverture → statut « en cours ») par période.
    - Délai moyen de résolution (ouverture → clôture) par catégorie.
    - Nombre de tickets créés par mois, par catégorie et par bâtiment (courbe et camembert).
    - Taux de tickets résolus dans les 7 jours.
    - Nombre de votes et de participations aux sondages.
  - Filtres : période (mois, trimestre, année), bâtiment, catégorie de ticket.
  - Export des statistiques en CSV pour tableur externe.
  - Les données sont agrégées et anonymisées quant à l'identité des auteurs de tickets (seule la catégorie et le lot sont utilisés).

---

## Communauté

### EF-WEB-116 — Petites annonces entre résidents
- **Priorité :** Moyenne
- **Description :** Les résidents peuvent publier des annonces de vente, de don ou de recherche d'objets au sein de la résidence, favorisant l'entraide et le réemploi local.
- **Critères d'acceptance :**
  - Troisième onglet de la section Communauté (après Sondages et Boîte à idées).
  - Trois types d'annonce : **vente**, **don**, **recherche**.
  - Neuf catégories disponibles : mobilier, électroménager, bricolage, jardin, sport, enfants, vêtements, informatique, autre.
  - Chaque annonce comporte : titre, description (éditeur riche HTML sanitisé), type, catégorie, prix (optionnel, uniquement pour vente), négociable (oui/non), jusqu'à **5 photos** (upload multiple, preview avant envoi).
  - Cycle de vie des annonces : `disponible` → `réservé` → `vendu` (ou `archivé`). Seul l'auteur peut changer le statut.
  - L'auteur peut choisir de rendre ses coordonnées visibles (`contact_visible`).
  - Tout résident authentifié peut consulter les annonces ; seul l'auteur peut modifier ou supprimer ses propres annonces.
  - Le conseil syndical et l'admin peuvent modérer (archiver) toute annonce inappropriée.
  - La liste affiche les annonces disponibles en priorité, puis les réservées. Les annonces vendues/archivées ne sont visibles que par l'auteur.

### EF-WEB-117 — Annonces de hall (affiches PDF du Conseil Syndical)
- **Priorité :** Moyenne
- **Description :** Le conseil syndical produit depuis son espace une affiche PDF à la charte de la résidence, destinée aux panneaux d'affichage des halls, et la transmet par email aux membres du CS chargés de l'imprimer et de l'afficher.
- **Critères d'acceptance :**
  - Onglet **Annonces Hall** de l'Espace CS, entre *Reporting* et *Annuaire*, réservé au CS et à l'admin.
  - Saisie : titre, message (éditeur riche HTML sanitisé), périmètre d'affichage (composant périmètre commun) et **au plus 2 photos facultatives** (composant de galerie commun à la Communauté). Le **texte est l'élément central** de l'affiche : les photos sont placées en pied de contenu, à hauteur bridée, de façon à ce que le **format A4/A5 reste tenu** sur une page.
  - **Pré-remplissage depuis une actualité** : un sélecteur propose les **10 dernières actualités publiées** ; le choix recopie titre, contenu, périmètre **et photos** (image de l'actualité puis pièces jointes de type image, tronquées à 2) dans le formulaire, tous les champs restant modifiables avant validation. L'affiche produite est indépendante de l'actualité (aucune synchronisation ultérieure).
  - **Déclenchement depuis une publication** : une option **« Créer une annonce Hall »** s'ajoute aux options de publication existantes (WhatsApp, syndic, CS). Cochée, elle exécute le workflow complet (PDF, envoi au CS du périmètre, historique) à la publication — jamais sur un brouillon. Les photos de l'actualité alimentent l'affiche dans la même limite. Le déclenchement est **idempotent** : une publication ne génère qu'une seule affiche, tracée par `annonce_hall.publication_id`. Un échec de génération est journalisé et ne fait jamais échouer la publication.
  - **Format automatique** : le plus petit format normalisé accueillant le contenu (titre + message) est retenu, parmi **A4, A5, A6, A7, A8** — objectif : occuper le minimum de place dans l'afficheur du hall. Seuils : A8 ≤ 70 caractères, A7 ≤ 140, A6 ≤ 300, A5 ≤ 600, A4 au-delà. Le CS peut imposer un format. Sous l'A4, l'affiche porte un **liseré en pointillés** servant de trait de découpe. Une affiche portant une photo ne descend pas sous l'**A5** ; sous l'A6 le QR code disparaît du pied de page, sous l'A5 la date d'affichage également.
  - **Aperçu** avant envoi, rendu identique au PDF, sans enregistrement ni envoi.
  - À la création : PDF généré côté serveur (WeasyPrint), conservé sur disque, puis envoyé **en pièce jointe** via le template email `annonce_hall` aux membres du CS rattachés au périmètre (plus le gestionnaire du site). Un périmètre transverse (copropriété entière, parking, cave, AFUL) notifie l'ensemble du CS. Seuls les membres liés à un compte actif avec email sont notifiés ; l'auteur reçoit une copie cachée.
  - Le PDF est **figé** : une correction passe par une nouvelle annonce, jamais par une régénération.
  - **Historique** : date, titre, vignette, périmètre, format, taille et téléchargement du PDF ; aperçu du message au déploiement de la carte ; renvoi possible au CS.
  - **Archivage** par le CS (l'annonce bascule dans le filtre *Archives*) ; **suppression définitive** (ligne + PDF + illustration) réservée à l'admin depuis les archives, conformément au pattern « Archiver vs Supprimer ».

---

## Espace bailleur — Gestion locative

### EF-WEB-120 — Gestion des baux et locataires
- **Priorité :** Haute
- **Description :** Un copropriétaire bailleur gère ses baux locatifs directement depuis l'application : création de bail, suivi de l'occupation et terminaison.
- **Critères d'acceptance :**
  - Un onglet « Mes Lots » dans l'espace bailleur affiche tous les lots possédés, avec pour chacun : le locataire actif (ou « Vacant »), les dates d'entrée et de sortie prévue, et le statut du bail (`actif`, `en_cours_sortie`, `terminé`).
  - Chaque lot affiche un label enrichi (`lotLabel`) : type de lot, numéro, bâtiment et étage (ex. « Appartement T3 — Lot 42, Bât. A, 2ᵉ étage »).
  - Création d'un bail : le bailleur renseigne le locataire (existant via recherche ou libre saisie nom/prénom/email/téléphone), la date d'entrée, la date de sortie prévue (optionnelle) et des notes.
  - Si le locataire recherché correspond à un utilisateur existant, le champ `locataire_id` est renseigné automatiquement ; sinon les coordonnées en texte libre sont stockées.
  - Terminaison de bail : le bailleur renseigne la date de sortie réelle, le statut passe à `terminé`.
  - L'historique des baux terminés reste consultable par le bailleur.

### EF-WEB-121 — Recherche de locataire
- **Priorité :** Haute
- **Description :** Lors de la création d'un bail, le bailleur peut rechercher un locataire existant par nom ou email.
- **Critères d'acceptance :**
  - Un champ de recherche interroge l'API (`GET /bailleur/search-locataire?q=…`).
  - La recherche par **email** fait une correspondance exacte ; la recherche par **nom/prénom** fait une correspondance partielle (insensible à la casse).
  - Si plusieurs résultats correspondent, un sélecteur permet de choisir le bon locataire.
  - Si aucun résultat, le bailleur peut saisir les coordonnées manuellement (nom, prénom, email, téléphone).

### EF-WEB-122 — Création de bail multi-lots
- **Priorité :** Moyenne
- **Description :** Un bailleur possédant plusieurs lots peut créer un bail couvrant plusieurs lots en une seule opération (même locataire, même dates).
- **Critères d'acceptance :**
  - Le formulaire de création propose la sélection de **plusieurs lots** parmi les lots vacants du bailleur.
  - Les lots sont affichés avec leur label enrichi (`lotLabel`).
  - L'API crée un `LocationBail` distinct par lot sélectionné (endpoint `POST /bailleur/baux/creer-multi`).
  - Le locataire, les dates et les notes sont partagés entre tous les baux créés.

### EF-WEB-123 — Remise d'objets liée au bail
- **Priorité :** Moyenne
- **Description :** Le bailleur suit les objets (clés, télécommandes, vigiks) remis au locataire dans le cadre d'un bail.
- **Critères d'acceptance :**
  - Chaque bail possède une section « Remise d'objets » listant les objets remis.
  - Types d'objets : `clé`, `télécommande`, `vigik`, `autre`.
  - Pour chaque objet : libellé, quantité, référence optionnelle, date de remise, statut (`en_possession`, `rendu`, `perdu`, `non_remis`).
  - À la fin du bail, le bailleur peut pointer les objets rendus et constater les manquants.

---

## Accès & sécurité (compléments bailleur)

### EF-WEB-124 — Vue accès par locataire (bailleur)
- **Priorité :** Moyenne
- **Description :** Un copropriétaire bailleur peut consulter les accès (vigiks, télécommandes) actifs de ses locataires, pour chacun de ses lots.
- **Critères d'acceptance :**
  - Dans la section Accès & Badges, un onglet ou vue « Par locataire » regroupe les accès par locataire actif du bailleur.
  - Les informations affichées sont en lecture seule (le bailleur ne peut pas modifier les accès).
  - Si aucun locataire actif, la vue affiche un message « Aucun locataire actif sur vos lots ».
