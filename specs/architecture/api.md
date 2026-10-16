# Spécification API

> API REST FastAPI — Base URL configurée via CORS.  
> Authentification : JWT (access token 15 min + refresh token 7 j) en cookies HttpOnly.  
> Rate limiting : slowapi (middleware global).  
> Version : dérivée de `package.json` front.

---

## Authentification

- **Mécanisme :** JWT en cookies HttpOnly (`access_token` + `refresh_token`).
- **Access token :** 15 minutes, envoyé automatiquement via cookie.
- **Refresh token :** 7 jours, rotation à chaque `/auth/refresh` (ancien token révoqué).
- **Cookies :** `secure=True` (configurable via `COOKIE_SECURE`), `samesite=strict`, `httponly=True`.
- **Rate limiting :** endpoints auth protégés par slowapi (voir tableau ci-dessous).

---

## Health check

| Méthode | Chemin | Description | Auth |
|---------|--------|-------------|------|
| GET | `/health` | Statut API + version | Aucune |

---

## `/auth` — Authentification & profil

| # | Méthode | Chemin | Description | Auth | Rate limit |
|---|---------|--------|-------------|------|------------|
| 1 | GET | `/auth/batiments` | Liste publique des bâtiments (formulaire inscription) | Aucune | — |
| 2 | POST | `/auth/register` | Créer un compte | Aucune | **5/min** |
| 3 | POST | `/auth/login` | Connexion (set cookies access + refresh) | Aucune | **5/min** |
| 4 | POST | `/auth/refresh` | Rafraîchir le JWT (rotation du refresh token) | Cookie | **10/min** |
| 5 | POST | `/auth/logout` | Déconnexion (révoque refresh, supprime cookies) | Cookie | — |
| 6 | GET | `/auth/me` | Profil utilisateur connecté | Authentifié | — |
| 7 | PATCH | `/auth/me` | Mise à jour profil (prénom, nom, email, téléphone…) | Authentifié | — |
| 8 | POST | `/auth/me/demande-modification` | Demande de changement statut/bâtiment | Authentifié | — |
| 9 | GET | `/auth/me/demandes-modification` | Liste ses demandes de modification | Authentifié | — |
| 10 | POST | `/auth/change-password` | Changer son mot de passe | Authentifié | — |
| 11 | POST | `/auth/mot-de-passe-oublie` | Demande réinitialisation par email | Aucune | **3/min** |
| 12 | POST | `/auth/reinitialiser-mot-de-passe` | Réinitialiser le mot de passe via token | Aucune | **5/min** |

---

## `/admin` — Administration & espace CS

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/admin/comptes-en-attente` | Comptes inactifs | CS/Admin |
| 2 | GET | `/admin/comptes-en-attente/enrichis` | Comptes en attente + nb lots prévus import | CS/Admin |
| 3 | POST | `/admin/comptes/{user_id}/traiter` | Valider ou refuser un compte | CS/Admin |
| 4 | GET | `/admin/commandes-acces` | Commandes d'accès en attente | CS/Admin |
| 5 | POST | `/admin/commandes-acces/{cmd_id}/traiter` | Accepter / refuser commande accès ; `codes` à l'acceptation → badges posés sur le lot commandé (#1194) | CS/Admin |

| 6 | GET | `/admin/sauvegardes/config` | Config sauvegardes | Admin |
| 7 | PUT | `/admin/sauvegardes/config` | Mettre à jour config sauvegardes | Admin |
| 8 | POST | `/admin/sauvegardes/maintenant` | Sauvegarde immédiate (background) | Admin |
| 9 | GET | `/admin/sauvegardes/historique` | Historique des sauvegardes | Admin |
| 10 | POST | `/admin/maintenance/rapport` | Enregistrer rapport de maintenance cron | Clé maintenance |
| 11 | GET | `/admin/maintenance/historique` | Historique de maintenance (50 derniers) | Admin |
| 12 | GET | `/admin/modeles-email` | Liste modèles email | Admin |
| 13 | PATCH | `/admin/modeles-email/{modele_id}` | Modifier un modèle email | Admin |
| 16 | GET | `/admin/annuaire` | Annuaire public CS + syndic | Authentifié |
| 17 | GET | `/admin/annuaire/cs` | Composition CS (gestion) | CS/Admin |
| 18 | PUT | `/admin/annuaire/cs` | Remplacer la composition CS | CS/Admin |
| 19 | GET | `/admin/annuaire/syndic` | Infos syndic (gestion) | CS/Admin |
| 20 | PUT | `/admin/annuaire/syndic` | Remplacer les infos syndic | CS/Admin |
| 21 | GET | `/admin/utilisateurs` | Tous les utilisateurs + tags lots/tc/vigik/bail | CS/Admin |
| 22 | POST | `/admin/utilisateurs/{user_id}/ajouter-role` | Ajouter un rôle | Admin |
| 23 | POST | `/admin/utilisateurs/{user_id}/retirer-role` | Retirer un rôle | Admin |
| 24 | GET | `/admin/demandes-profil` | Demandes de modification profil en attente | CS/Admin |
| 25 | POST | `/admin/demandes-profil/{demande_id}/traiter` | Approuver/rejeter demande profil | CS/Admin |
| 26 | PATCH | `/admin/utilisateurs/{user_id}` | Modifier infos utilisateur | Admin |
| 27 | DELETE | `/admin/utilisateurs/{user_id}` | Supprimer un utilisateur | Admin |
| 28 | POST | `/admin/utilisateurs/{user_id}/changer-role` | Remplacer tous les rôles | Admin |
| 29 | POST | `/admin/utilisateurs/{user_id}/accueil-arrivant` | Accueil nouvel arrivant (notifs + email syndic) | CS/Admin |
| 30 | PATCH | `/admin/utilisateurs/{user_id}/ban-sondages` | Interdire/réautoriser sondages | Admin |
| 31 | POST | `/admin/baux/{bail_id}/lier-locataire/{user_id}` | Lier manuellement locataire à bail | CS/Admin |
| 32 | GET | `/admin/baux` | Tous les baux actifs | CS/Admin |

---

## `/acces` — Badges, télécommandes & imports

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/acces/mes-vigiks` | Vigiks de l'utilisateur | Authentifié |
| 2 | GET | `/acces/mes-telecommandes` | Télécommandes de l'utilisateur | Authentifié |
| 3 | GET | `/acces/mes-commandes` | Commandes d'accès de l'utilisateur | Authentifié |
| 4 | POST | `/acces/commandes` | Créer commande d'accès (notifie CS) | Authentifié |
| 5 | PATCH | `/acces/vigiks/{vigik_id}/perdu` | Signaler vigik perdu | Authentifié |
| 6 | PATCH | `/acces/telecommandes/{tc_id}/perdu` | Signaler télécommande perdue | Authentifié |
| 7 | DELETE | `/acces/vigiks/{vigik_id}` | Supprimer un vigik | Authentifié |
| 8 | DELETE | `/acces/telecommandes/{tc_id}` | Supprimer une télécommande | Authentifié |
| 9 | POST | `/acces/declarer-badge` | Déclarer un badge existant | Authentifié |
| 10 | GET | `/acces/admin/vigiks` | Tous les vigiks | CS/Admin |
| 11 | GET | `/acces/admin/telecommandes` | Toutes les télécommandes | CS/Admin |
| 12 | PATCH | `/acces/admin/vigiks/{vigik_id}` | Modifier statut vigik | CS/Admin |
| 13 | POST | `/acces/admin/vigiks` | Créer un vigik manuellement | CS/Admin |
| 14 | POST | `/acces/admin/telecommandes` | Créer une télécommande manuellement | CS/Admin |
| 15 | POST | `/acces/admin/imports/upload` | Upload Excel télécommandes (staging) | CS/Admin |
| 16 | GET | `/acces/admin/imports` | Liste imports télécommandes | CS/Admin |
| 17 | POST | `/acces/admin/imports/auto-match` | Retrouve le LOT des lignes (nom du copropriétaire dans le fichier des lots), puis les comptes | CS/Admin |
| 17 bis | POST | `/acces/admin/imports/rattacher` | Rattachement en masse : chaque ligne dont le lot est connu (#1194) | CS/Admin |
| 18 | PATCH | `/acces/admin/imports/{import_id}` | Modifier liaisons d'un import TC | CS/Admin |
| 19 | POST | `/acces/admin/imports/{import_id}/resoudre` | Rattache la télécommande à son LOT — plus aucun compte exigé (#1194) | CS/Admin |
| 20 | POST | `/acces/admin/imports/{import_id}/ignorer` | Ignorer un import TC | CS/Admin |
| 21 | POST | `/acces/admin/imports/{import_id}/remettre-en-attente` | Remettre import ignoré en attente | CS/Admin |
| 21 bis | DELETE | `/acces/admin/imports/{import_id}` | Supprimer une ligne erronée — le badge éventuel reste au parc | Admin |
| 22 | POST | `/acces/admin/imports/{import_id}/refuser-locataire` | Locataire refuse la TC | CS/Admin |
| 23 | GET | `/acces/admin/imports/stats` | Statistiques imports TC | CS/Admin |
| 24 | POST | `/acces/admin/imports-vigik/upload` | Upload Excel vigiks (staging) | CS/Admin |
| 25 | GET | `/acces/admin/imports-vigik/stats` | Statistiques imports vigik | CS/Admin |
| 26 | GET | `/acces/admin/imports-vigik` | Liste imports vigik | CS/Admin |
| 27 | POST | `/acces/admin/imports-vigik/auto-match` | Retrouve le LOT des lignes (bâtiment + appartement), puis les comptes | CS/Admin |
| 27 bis | POST | `/acces/admin/imports-vigik/rattacher` | Rattachement en masse : chaque ligne dont le lot est connu (#1194) | CS/Admin |
| 27 ter | GET | `/acces/admin/imports-lots` | Les lots, avec le copropriétaire que le fichier des lots leur donne — pour choisir le lot d'une ligne | CS/Admin |
| 28 | PATCH | `/acces/admin/imports-vigik/{import_id}` | Modifier liaisons import vigik | CS/Admin |
| 29 | POST | `/acces/admin/imports-vigik/{import_id}/resoudre` | Rattache le Vigik à son LOT — plus aucun compte exigé (#1194) | CS/Admin |

| 30 | POST | `/acces/admin/imports-vigik/{import_id}/ignorer` | Ignorer un import vigik | CS/Admin |
| 30 bis | DELETE | `/acces/admin/imports-vigik/{import_id}` | Supprimer une ligne erronée — le badge éventuel reste au parc | Admin |

---

## `/annonces` — Petites annonces (Communauté)

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/annonces` | Liste petites annonces (hors archivées) | Authentifié |
| 2 | POST | `/annonces` | Créer une annonce | Authentifié |
| 3 | PATCH | `/annonces/{annonce_id}` | Modifier une annonce (auteur/CS/admin) | Authentifié |
| 4 | PATCH | `/annonces/{annonce_id}/statut` | Changer statut annonce | Authentifié |
| 5 | DELETE | `/annonces/{annonce_id}` | Supprimer une annonce | Authentifié |
| 6 | POST | `/annonces/{annonce_id}/photo` | Ajouter une photo (max 5) | Authentifié |
| 7 | DELETE | `/annonces/{annonce_id}/photo` | Retirer une photo | Authentifié |

---

## `/bailleur` — Gestion locative

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/bailleur/mes-baux` | Baux du bailleur connecté | Bailleur/CS/Admin |
| 3 | POST | `/bailleur/baux/creer-multi` | Créer bail sur plusieurs lots | Bailleur/CS/Admin |
| 4 | GET | `/bailleur/baux/{bail_id}` | Détail d'un bail | Bailleur/CS/Admin |
| 5 | PATCH | `/bailleur/baux/{bail_id}` | Modifier un bail | Bailleur/CS/Admin |
| 6 | POST | `/bailleur/baux/{bail_id}/terminer` | Terminer un bail (retour accès auto) | Bailleur/CS/Admin |
| 7 | GET | `/bailleur/search-locataire` | Rechercher locataire par nom/email | Bailleur/CS/Admin |

---

## `/calendrier` — Événements de la résidence

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/calendrier` | Liste événements (AG filtrée par rôle) | Authentifié |
| 3 | POST | `/calendrier` | Créer un événement (notifie si coupure/travaux) | CS/Admin |
| 4 | PATCH | `/calendrier/{ev_id}` | Modifier un événement | CS/Admin |
| 5 | DELETE | `/calendrier/{ev_id}` | Supprimer un événement | Admin |

---

## `/config` — Configuration & WhatsApp

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/config` | Config UI publique (hors legal/private) | Aucune |
| 2 | GET | `/config/admin` | Toute la config (admin) | Admin |
| 3 | GET | `/config/legal` | Pages légales (mentions, politique) | Aucune |
| 4 | PUT | `/config` | Sauvegarder clés de config, dont les notifications site (`notify_ticket_bug_email`, `notify_new_user_created_email`) | Admin |
| 5 | GET | `/config/whatsapp-scheduled` | Messages WhatsApp planifiés | Admin |
| 6 | PUT | `/config/whatsapp-scheduled/{item_id}` | Modifier message WA planifié | Admin |
| 7 | GET | `/config/whatsapp-logs` | 6 derniers envois WhatsApp | Admin |
| 8 | POST | `/config/whatsapp-test` | Envoyer message WA de test | Admin |
| 9 | GET | `/config/whatsapp-status` | État connexion WhatsApp | Admin |
| 10 | POST | `/config/smtp-test` | Envoyer email de test | Admin |

---

## `/copropriete` — Fiche copropriété & bâtiments

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/copropriete` | Fiche copropriété | Authentifié |
| 2 | PATCH | `/copropriete` | Modifier fiche copropriété | Admin |
| 3 | GET | `/copropriete/batiments` | Liste bâtiments | Authentifié |
| — | ~~GET~~ | ~~`/copropriete/lots`~~ | Retirée le 23/09/2026 (#1194) : elle donnait le propriétaire de chaque lot à tout résident. Voir `/acces/admin/imports-lots` | — |

---

## `/diagnostics` — Diagnostics immobiliers

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/diagnostics/types` | Types de diagnostic + rapports | Authentifié |
| 2 | PATCH | `/diagnostics/types/{type_id}/non-applicable` | Toggle non-applicable | CS/Admin |
| 3 | POST | `/diagnostics/types/{type_id}/rapports` | Upload rapport diagnostic | CS/Admin |
| 4 | PATCH | `/diagnostics/rapports/{rapport_id}` | Modifier métadonnées rapport | CS/Admin |
| 5 | DELETE | `/diagnostics/rapports/{rapport_id}` | Supprimer rapport + fichier | CS/Admin |
| 6 | GET | `/diagnostics/rapports/{rapport_id}/télécharger` | Télécharger fichier rapport | Authentifié |

---

## `/documents` — Bibliothèque documentaire

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/documents/categories` | Catégories de documents accessibles | Authentifié |
| 2 | GET | `/documents` | Liste documents (filtré par ACL 3 couches) | Authentifié |
| 3 | GET | `/documents/{doc_id}/télécharger` | Télécharger document (contrôle accès) | Authentifié |
| 4 | PATCH | `/documents/{doc_id}` | Modifier métadonnées document | CS/Admin |
| 5 | POST | `/documents` | Upload document | CS/Admin |
| 6 | DELETE | `/documents/{doc_id}` | Supprimer document + fichier | CS/Admin |

---

## `/faq` — Foire aux questions

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/faq` | FAQ actives (triées catégorie + ordre) | Authentifié |
| 2 | GET | `/faq/all` | Toutes les FAQ (actives + inactives) | CS/Admin |
| 3 | POST | `/faq` | Créer entrée FAQ | CS/Admin |
| 4 | PATCH | `/faq/{item_id}` | Modifier entrée FAQ | CS/Admin |
| 5 | DELETE | `/faq/{item_id}` | Supprimer entrée FAQ | CS/Admin |

---

## `/idees` — Boîte à idées (Communauté)

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/idees` | Liste idées + votes | Authentifié |
| 2 | POST | `/idees` | Soumettre une idée | Authentifié |
| 3 | POST | `/idees/{idee_id}/voter` | Voter / retirer vote (toggle) | Authentifié |
| 4 | PATCH | `/idees/{idee_id}/statut` | Changer statut idée | CS/Admin |

---

## `/lots` — Lots & imports

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/lots/mes-lots` | Lots activement rattachés au compte (aucun repli par rôle — le patrimoine entier : `/lots/admin/tous`) | Authentifié |
| 2 | GET | `/lots/admin/tous` | Tous les lots | CS/Admin |
| 4 | GET | `/lots/commandes-acces/mes-commandes` | Commandes accès de l'utilisateur | Authentifié |
| 5 | POST | `/lots/commandes-acces` | Créer commande d'accès | Authentifié |
| 6 | POST | `/lots/admin/imports/upload` | Upload Excel lots (staging + auto-match) | CS/Admin |
| 7 | GET | `/lots/admin/imports` | Liste imports lots | CS/Admin |
| 8 | GET | `/lots/admin/imports/stats` | Statistiques imports lots | CS/Admin |
| 9 | PATCH | `/lots/admin/imports/{imp_id}` | Modifier liaisons import lot | CS/Admin |
| 10 | POST | `/lots/admin/imports/{imp_id}/resoudre` | Résoudre import → créer Lot + UserLot | CS/Admin |
| 11 | POST | `/lots/admin/imports/{imp_id}/ignorer` | Ignorer un import lot | CS/Admin |
| 12 | POST | `/lots/admin/imports/auto-resoudre` | Auto-résoudre tous les imports copropriétaires | CS/Admin |
| 13 | POST | `/lots/admin/imports/auto-match` | Auto-match imports lots → Lot + Utilisateur | CS/Admin |

---

## `/notifications` — Notifications in-app

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/notifications` | Notifications de l'utilisateur | Authentifié |
| 2 | PATCH | `/notifications/{notif_id}/lue` | Marquer une notification lue | Authentifié |
| 3 | POST | `/notifications/tout-marquer-lu` | Tout marquer lu | Authentifié |
| 4 | DELETE | `/notifications/{notif_id}` | Supprimer notification | Authentifié |

---

## `/prestataires` — Prestataires, contrats, devis & compteurs

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/prestataires` | Prestataires actifs | CS/Admin |
| 2 | POST | `/prestataires` | Créer prestataire | CS/Admin |
| 3 | PATCH | `/prestataires/{p_id}` | Modifier prestataire | CS/Admin |
| 4 | DELETE | `/prestataires/{p_id}` | Archiver prestataire (soft delete) | CS/Admin |
| 5 | GET | `/prestataires/contrats` | Contrats d'entretien actifs | CS/Admin |
| 6 | POST | `/prestataires/contrats` | Créer contrat | CS/Admin |
| 7 | PATCH | `/prestataires/contrats/{c_id}` | Modifier contrat | CS/Admin |
| 8 | DELETE | `/prestataires/contrats/{c_id}` | Archiver contrat (soft delete) | CS/Admin |
| 9 | GET | `/prestataires/devis` | Devis actifs | CS/Admin |
| 10 | POST | `/prestataires/devis` | Créer devis/prestation | CS/Admin |
| 11 | PATCH | `/prestataires/devis/{d_id}` | Modifier devis | CS/Admin |
| 12 | DELETE | `/prestataires/devis/{d_id}` | Archiver devis | CS/Admin |
| 13 | POST | `/prestataires/devis/{d_id}/fichier` | Upload fichier joint devis | CS/Admin |
| 14 | DELETE | `/prestataires/devis/{d_id}/fichier` | Supprimer fichier joint devis | CS/Admin |
| 15 | POST | `/prestataires/devis/{d_id}/os` | Upload ordre de service (→ statut accepté) | CS/Admin |
| 16 | GET | `/prestataires/releves` | Relevés compteurs | CS/Admin |
| 17 | POST | `/prestataires/releves` | Créer relevé compteur | CS/Admin |
| 18 | PATCH | `/prestataires/releves/{r_id}` | Modifier relevé | CS/Admin |
| 19 | DELETE | `/prestataires/releves/{r_id}` | Supprimer relevé | CS/Admin |
| 20 | POST | `/prestataires/releves/{r_id}/photo` | Upload photo relevé | CS/Admin |
| 21 | GET | `/prestataires/compteurs-config` | Config compteurs actifs | CS/Admin |
| 22 | POST | `/prestataires/compteurs-config` | Créer type compteur | CS/Admin |
| 23 | PATCH | `/prestataires/compteurs-config/{cfg_id}` | Modifier type compteur | CS/Admin |

---

## `/publications` — Actualités & évolutions

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/publications` | Liste publications (avec auto-purge annulées) | Authentifié |
| 2 | POST | `/publications` | Créer publication (+ WhatsApp si activé ; si image + partage, publication finale après upload image) | CS/Admin |
| 3 | PATCH | `/publications/{pub_id}` | Modifier publication, y compris publication d'un brouillon après upload image | CS/Admin |
| 4 | DELETE | `/publications/{pub_id}` | Supprimer publication + évolutions | Admin |
| 5 | POST | `/publications/{pub_id}/evolutions` | Ajouter évolution (commentaire ou état) | CS/Admin |

---

## `/sondages` — Sondages (Communauté)

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/sondages` | Liste sondages accessibles (filtré profil/bâtiment) | Authentifié |
| 2 | GET | `/sondages/{sondage_id}` | Détail sondage + options + votes + commentaires | Authentifié |
| 3 | POST | `/sondages` | Créer sondage + options (notifie ciblés) | CS/Admin |
| 4 | POST | `/sondages/{sondage_id}/voter` | Voter (+ commentaire optionnel) | Authentifié |
| 5 | POST | `/sondages/{sondage_id}/commenter` | Ajouter commentaire | Authentifié |
| 6 | DELETE | `/sondages/{sondage_id}/commentaires/{cid}` | Supprimer commentaire (auteur/CS/admin) | Authentifié |
| 7 | PATCH | `/sondages/{sondage_id}` | Modifier sondage (auteur/admin) | Authentifié |
| 8 | DELETE | `/sondages/{sondage_id}` | Supprimer sondage + cascade | Authentifié |
| 9 | PATCH | `/sondages/{sondage_id}/cloturer` | Clôturer immédiatement | Authentifié |

---

## `/tickets` — Demandes & signalements

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | GET | `/tickets` | Tickets (CS/admin = tous, résident = les siens) | Authentifié |
| 2 | POST | `/tickets` | Créer ticket (notifie CS ; e-mail syndic avec photos en PJ + CC rôle `conseil_syndical`) | Authentifié |
| 2 bis | POST | `/tickets/lot` | « Init. prestataires » : visites Entretien de l'exercice en une transaction, sans aucune diffusion (#1193) | CS/Admin |
| 3 | GET | `/tickets/{ticket_id}` | Détail ticket | Authentifié |
| 4 | PATCH | `/tickets/{ticket_id}` | Modifier statut/priorité (auto-évolution) | CS/Admin |
| 5 | GET | `/tickets/{ticket_id}/messages` | Messages du ticket (internes filtrés) | Authentifié |
| 6 | POST | `/tickets/{ticket_id}/messages` | Ajouter message (+ auto-évolution) | Authentifié |
| 7 | GET | `/tickets/{ticket_id}/evolutions` | Fil de suivi ticket | Authentifié |
| 8 | POST | `/tickets/{ticket_id}/evolutions` | Ajouter évolution manuelle | CS/Admin |
| 9 | DELETE | `/tickets/{ticket_id}` | Supprimer ticket + messages + évolutions | Admin |

---

## `/uploads` — Fichiers (avatars, photos résidence, publications)

| # | Méthode | Chemin | Description | Auth |
|---|---------|--------|-------------|------|
| 1 | POST | `/uploads/avatar` | Photo de profil (400 px max) | Authentifié |
| 2 | POST | `/uploads/residence` | Photo résidence (1600 px max) | CS/Admin |
| 3 | POST | `/uploads/publication/{pub_id}` | Image publication (1200 px max), utilisée avant partage WhatsApp avec photo | CS/Admin |

---

## Résumé

| Routeur | Préfixe | Endpoints | Niveau d'auth |
|---------|---------|-----------|---------------|
| system | `/` | 1 | Aucune |
| auth | `/auth` | 12 | Mixte (public + authentifié) |
| admin | `/admin` | 32 | CS/Admin ou Admin |
| acces | `/acces` | 30 | Authentifié + CS/Admin |
| annonces | `/annonces` | 7 | Authentifié |
| bailleur | `/bailleur` | 7 | Bailleur/CS/Admin |
| calendrier | `/calendrier` | 5 | Authentifié + CS/Admin |
| config | `/config` | 10 | Mixte (public + admin) |
| copropriete | `/copropriete` | 4 | Authentifié + Admin |
| diagnostics | `/diagnostics` | 6 | Authentifié + CS/Admin |
| documents | `/documents` | 6 | Authentifié (ACL 3 couches) + CS/Admin |
| faq | `/faq` | 5 | Authentifié + CS/Admin |
| idees | `/idees` | 4 | Authentifié |
| lots | `/lots` | 13 | Authentifié + CS/Admin |
| notifications | `/notifications` | 4 | Authentifié |
| prestataires | `/prestataires` | 23 | CS/Admin |
| publications | `/publications` | 5 | Authentifié + CS/Admin |
| sondages | `/sondages` | 9 | Authentifié |
| tickets | `/tickets` | 9 | Authentifié + CS/Admin |
| uploads | `/uploads` | 3 | Authentifié + CS/Admin |
| **Total** | | **195** | |

---

## Dépendances d'autorisation

**Toutes** définies dans `api/app/auth/deps.py` — source unique. Aucune dépendance
d'autorisation ne doit être définie ailleurs : une règle locale à un routeur échappe
à tout durcissement du module central. Vérifié automatiquement par
`api/tests/test_autorisation.py`.

| Dépendance | Rôle requis |
|------------|-------------|
| `get_current_user` | Tout utilisateur authentifié |
| `require_proprietaire` | Propriétaire, conseil syndical ou admin |
| `require_cs_or_admin` | Conseil syndical ou admin |
| `require_admin` | Admin uniquement |
| `ma_notification` | Destinataire de la notification (appartenance d'un objet) |
| `x-maintenance-key` | En-tête à secret partagé (cron machine-à-machine, hors système de rôles) |

> **Corrigé le 02/10/2026 (#1534).** Ce tableau documentait `get_acting_user`
> (« délégation via en-tête `X-Acting-As` ») et `require_role(*roles)`. Aucune
> route n'avait jamais pris l'une ni l'autre : l'aidant qui choisissait « Agir
> pour… » écrivait sous sa propre identité. Les deux sont retirées, et la
> délégation est en **lecture seule** (`utils/delegations_actives`).
> `test_autorisation.py` refuse désormais une dépendance qu'aucune route ne prend.

> **Corrigé le 26/07/2026.** Ce tableau documentait `_require_bailleur`, une
> dépendance définie **localement** dans `routers/bailleur.py` et doublon exact de
> `require_proprietaire` (mêmes trois rôles, même message). 17 endpoints s'appuyaient
> dessus. La spec légitimait donc la dérive au lieu de la signaler. Les endpoints
> utilisent désormais `require_proprietaire`.

Les contrôles de rôle passent par `user.has_role(RoleUtilisateur.…)` — **jamais**
par `user.role`, qui ne porte que le rôle principal et manquerait un admin dont le
rôle principal est autre. Jamais de chaîne littérale non plus : une faute de frappe
y est silencieuse.

### Endpoints publics (sans authentification)

Liste exhaustive et volontaire, verrouillée par `_PUBLICS_ASSUMES` dans
`api/tests/test_autorisation.py`. Y ajouter une entrée est une décision de sécurité.

| Endpoint | Pourquoi public |
|---|---|
| `/auth/{login,register,refresh,logout}` | Impossible d'exiger une session pour ouvrir une session |
| `/auth/{mot-de-passe-oublie,reinitialiser-mot-de-passe}` | Parcours de récupération de compte |
| `/auth/{verifier-email,renvoyer-verification}` | Vérification d'adresse |
| `/auth/batiments` | Alimente le formulaire d'inscription |
| `GET /config` | Coquille d'interface — filtrée par **liste blanche** (voir ci-dessous) |
| `GET /config/legal` | Mentions légales et politique de confidentialité |
| `POST /telemetry/collect` | `sendBeacon`, visiteurs anonymes compris ; rattache l'événement au compte s'il y en a un, par `utilisateur_ou_anonyme` (`auth/deps.py`, jamais un décodage local — #1595) ; refus du profil honoré côté serveur et navigateur ; `LIMITE_COLLECTE_AUDIENCE` par minute et par jour, 20 événements et champs bornés, refus en bloc (#1597) |
| `POST /admin/maintenance/rapport` | Cron machine-à-machine ; secret partagé, refuse tout si la clé n'est pas configurée |

`GET /config` filtre par **liste blanche** (`_PUBLIC_KEYS`), jamais par liste noire :
une liste noire publie par défaut toute clé nouvelle. Elle exposait ainsi 31 clés
sans authentification — configuration SMTP, URL interne du bridge WhatsApp,
identifiant du groupe privé, référence de copropriété, et un lien d'invitation
fonctionnel au groupe WhatsApp des résidents. La configuration complète est réservée
à `GET /config/admin` (`require_admin`).
