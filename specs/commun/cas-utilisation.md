# Cas d'utilisation

> Cas d'utilisation principaux, communs au site web et à l'application mobile (PWA).

## CU-001 — Inscription et création de compte

- **Acteur :** Tout utilisateur (résident, copropriétaire, bailleur, locataire, syndic, mandataire)
- **Préconditions :** L'application est accessible ; l'utilisateur n'a pas encore de compte.
- **Description :**
  1. L'utilisateur accède à l'application et choisit « Créer un compte ».
  2. Il saisit les informations **obligatoires** :
     - Nom, Prénom
     - Email
     - Téléphone
     - Mot de passe OU authentification via Apple / Google (OAuth standard)
     - Profil d'utilisateur : locataire, copropriétaire bailleur, copropriétaire résident, syndic, mandataire
     - Bâtiment (non requis pour les profils syndic et mandataire)
     - Si profil **syndic** ou **mandataire** : Société et Fonction (tous deux obligatoires)
     - Rôle (uniquement si **copropriétaire**) : membre du conseil syndical (élu en AG, saisi par l'admin), admin (tous les droits)
       > Un locataire, un mandataire ou un syndic ne peut jamais être admin ni membre du conseil syndical.
  3. Il peut renseigner les informations **optionnelles** :
     - Photo ou avatar
     - Étage
     - Numéro(s) de lot avec type (appartement, cave, parking) et type d'appartement (Studio, T1, …)
     - Photos de son bien
  4. Si **copropriétaire bailleur** : son adresse réelle avec au minimum téléphone ou email obligatoires.
  5. Si **locataire** : indiquer le copropriétaire bailleur (validation requise par ce dernier s'il est enregistré).
  6. Le système compare le nom avec la liste des copropriétaires importée :
     - Nom reconnu → compte activé automatiquement.
     - Nom inconnu → validation par un membre du conseil syndical (de préférence celui du même bâtiment).
- **Postconditions :** Le compte est créé (actif ou en attente de validation) ; l'utilisateur accède à son espace personnel.
- **Scénarios alternatifs :**
  - Nom non reconnu et aucun membre du conseil syndical disponible → compte en attente de validation manuelle.
  - Email déjà utilisé → message d'erreur, proposition de récupération de mot de passe.
  - Profil syndic/mandataire sans société ni fonction → erreur de formulaire explicite.

---

## CU-005 — Onboarding progressif post-inscription

- **Acteur :** Tout nouvel utilisateur venant de créer son compte.
- **Préconditions :** Le compte est activé (auto ou par validation CS).
- **Description :**
  1. À la première connexion, l'application affiche un assistant en 4 étapes non bloquantes :
     - Étape 1 : « Complétez votre profil » (photo, lot, étage) — skippable.
     - Étape 2 : « Découvrez votre résidence » (plan, règlement, contacts) — lecture rapide.
     - Étape 3 : « Activez vos notifications » — opt-in, skippable.
     - Étape 4 : « Votre tableau de bord est prêt » — lien vers les raccourcis utiles.
  2. La progression est sauvegardée. L'assistant peut être relancé depuis le profil.
  3. Une barre de complétion du profil (%) reste visible sur le tableau de bord jusqu'à 100 %.
- **Postconditions :** L'utilisateur a un tableau de bord personnalisé et non vide.
- **Scénarios alternatifs :** L'utilisateur ignore toutes les étapes → espace personnalisé minimal mais fonctionnel, barre de progression visible.

---

## CU-006 — Validation d'un locataire par le copropriétaire bailleur

- **Acteur :** Copropriétaire bailleur + locataire en attente.
- **Préconditions :** Un locataire vient de s'inscrire en désignant ce copropriétaire comme bailleur.
- **Description :**
  1. Le copropriétaire bailleur reçoit une notification : « [Nom] souhaite s'inscrire en tant que locataire de votre lot [X] — Confirmer ou refuser ».
  2. Il consulte les informations saisies par le locataire et valide ou refuse.
  3. En cas de validation : le locataire accède à son espace.
  4. En cas de refus : le locataire est notifié du refus avec la possibilité de corriger ses informations ou de contacter le CS.
  5. Si le bailleur ne répond pas dans 7 jours, la demande est transmise au CS pour arbitrage.
- **Postconditions :** Le locataire est activé (ou refusé) et le lien lot ↔ locataire est établi.

---

## CU-007 — Validation en masse par le conseil syndical (vigiks, comptes)

- **Acteur :** Membre du conseil syndical.
- **Préconditions :** Des demandes de validation sont en attente (vigiks, nouveaux comptes).
- **Description :**
  1. Depuis son tableau de bord CS, le membre voit la liste des éléments en attente.
  2. Il peut cocher plusieurs éléments et les valider (ou refuser) en une seule action.
  3. Chaque demandeur reçoit une notification individuelle du résultat.
  4. Un motif de refus peut être saisi (appliqué à tous les items refusés ou personnalisé par item).
- **Postconditions :** Toutes les demandes sélectionnées sont traitées en un seul geste.

---

## CU-002 — Import initial des données (initialisation de l'application)

- **Acteur :** Administrateur (membre du conseil syndical ou responsable technique)
- **Préconditions :** L'application vient d'être installée ; aucun résident n'est encore enregistré.
- **Description :**
  1. L'administrateur importe la liste de tous les copropriétaires (fichier CSV ou saisie manuelle) → permet l'auto-validation lors des inscriptions.
  2. L'administrateur importe la liste de tous les **vigiks** (badges d'accès).
  3. L'administrateur importe la liste de toutes les **télécommandes de parking**.
- **Postconditions :** Les données de référence sont disponibles ; les inscriptions de résidents peuvent être auto-validées.
- **Scénarios alternatifs :**
  - Fichier d'import invalide → message d'erreur avec indication du format attendu.

---

## CU-003 — Soumettre une demande (panne, nuisance, question)

- **Acteur :** Résident authentifié
- **Préconditions :** Le résident est connecté.
- **Description :**
  1. Le résident accède à la section « Tickets ».
  2. Il crée un ticket en choisissant la catégorie (panne, nuisance, question, urgence, bug).
  3. Il décrit le problème et peut joindre des photos.
  4. Le conseil syndical est notifié de la nouvelle demande.
  5. Le résident suit le statut de sa demande et les échanges.
- **Postconditions :** La demande est enregistrée et visible par les parties concernées.
- **Scénarios alternatifs :**
  - Urgence (inondation, panne majeure) → notification prioritaire immédiate au conseil syndical.
  - Si l'auteur est un **locataire** : tous les copropriétaires bailleurs du lot concerné et le mandataire (éventuel) sont notifiés à la création et à chaque changement de statut.

---

## CU-004 — Commander un vigik ou une télécommande

- **Acteur :** Résident authentifié
- **Préconditions :** Le résident est connecté ; il a au moins un lot déclaré.
- **Description :**
  1. Le résident accède à « Accès & badges ».
  2. Il consulte ses accès actuels et l'historique.
  3. Il soumet une demande de nouveau vigik ou de nouvelle télécommande.
  4. Le conseil syndical traite la demande.
- **Postconditions :** La commande est enregistrée et traitée par le conseil syndical.
- **Scénarios alternatifs :**
  - Quota de vigiks dépassé → message d'information sur les règles en vigueur.

---

## CU-008 — Créer un bail locatif (bailleur)

- **Acteur :** Copropriétaire bailleur
- **Préconditions :** Le bailleur est authentifié et possède au moins un lot.
- **Description :**
  1. Le bailleur accède à « Espace bailleur → Mes Lots ».
  2. Il sélectionne un ou plusieurs lots vacants et clique « Créer un bail ».
  3. Il recherche un locataire existant par email ou nom (EF-WEB-121). Si trouvé, le locataire est lié automatiquement. Sinon, il saisit les coordonnées manuellement (nom, prénom, email, téléphone).
  4. Il renseigne la date d'entrée, la date de sortie prévue (optionnelle) et des notes.
  5. Si plusieurs lots sont sélectionnés, un bail distinct est créé par lot (même locataire, mêmes dates) via `POST /bailleur/baux/creer-multi`.
  6. Le bailleur peut ensuite ajouter les objets remis (clés, télécommandes, vigiks) via la section « Remise d'objets » du bail.
- **Postconditions :** Le(s) bail(s) sont créé(s) avec statut `actif`. Le lot apparaît comme « Occupé » dans la liste.
- **Scénarios alternatifs :**
  - Lot déjà occupé (bail actif existant) → erreur « Un bail actif existe déjà pour ce lot ».
  - Recherche locataire sans résultat → saisie libre des coordonnées.
  - Bail multi-lots : un des lots a déjà un bail actif → création bloquée pour ce lot, les autres sont créés.

---

## CU-009 — Publier une petite annonce

- **Acteur :** Résident authentifié (copropriétaire ou locataire)
- **Préconditions :** Le résident est connecté.
- **Description :**
  1. Le résident accède à « Communauté → Petites annonces ».
  2. Il crée une annonce en choisissant le type (vente, don, recherche) et la catégorie.
  3. Il renseigne le titre, la description (éditeur riche), le prix éventuel et peut joindre jusqu'à 5 photos.
  4. Il choisit si ses coordonnées sont visibles des autres résidents.
  5. L'annonce est publiée immédiatement avec le statut `disponible`.
  6. L'auteur peut ensuite passer l'annonce en `réservé`, `vendu` ou `archivé`.
- **Postconditions :** L'annonce est visible par tous les résidents de la copropriété.
- **Scénarios alternatifs :**
  - Plus de 5 photos → message d'erreur « Maximum 5 photos par annonce ».
  - Annonce signalée comme inappropriée → le CS ou l'admin peut l'archiver.

---

## CU-010 — Terminer un bail et restitution des objets

- **Acteur :** Copropriétaire bailleur
- **Préconditions :** Un bail actif existe pour le lot concerné.
- **Description :**
  1. Le bailleur accède au bail actif depuis « Espace bailleur → Mes Lots ».
  2. Il renseigne la date de sortie réelle.
  3. Il pointe les objets rendus (clés, télécommandes, vigiks) et constate les éventuels manquants.
  4. Le statut du bail passe à `terminé`.
  5. Le lot redevient « Vacant » dans la liste.
- **Postconditions :** Le bail est terminé, l'historique est conservé, les objets non rendus sont signalés.
- **Scénarios alternatifs :**
  - Objets non rendus → statut `perdu` ou `non_remis`, le bailleur en est informé.
