# Navigation et arborescence — Site web

> ⚠️ **Arborescence d'origine, périmée** : des pages décrites ici ont été fusionnées ou retirées (Accès & badges, Transparence & gouvernance, publications, calendrier). Le [manuel utilisateur](../../docs/manuel-utilisateur.html) et `front/src/lib/pages.ts` font foi.

> Structure des pages et navigation principale du site web (SvelteKit SSR/SPA).  
> La navigation s'adapte à la taille d'écran :
> - **Desktop (≥ 768 px)** : sidebar latérale fixe (220 px).
> - **Mobile (≤ 767 px)** : topbar fixe avec bouton ☰ (hamburger) ouvrant un overlay plein écran — la sidebar est masquée.

## Arborescence

```
Authentification
├── Connexion
├── Création de compte
└── Récupération de mot de passe

Onboarding (première connexion uniquement)
├── Étape 1 — Compléter le profil  (skippable)
├── Étape 2 — Découvrir la résidence  (skippable)
├── Étape 3 — Activer les notifications  (skippable)
└── Étape 4 — Votre tableau de bord est prêt

Tableau de bord (accueil résident)  (EF-WEB-005)
├── Hero (nom, lot, rôle)
├── Consignes de la copropriété (lien vers /residence, mis en avant pour locataires)
├── Raccourcis rapides (pilules de navigation)
├── Alertes urgentes (publications urgentes actives)
├── KPIs (tickets, événements, résolution, publications)
├── Prochaines échéances (expandables, filtrées par rôle/périmètre)
├── Fil d'activité — récent (< 30 j, expandables, dédupliqués des échéances)
├── Fil d'activité — anciens (30-377 j, accordéon replié)
└── [barre de complétion de profil si < 100 %]

[Barre de navigation — Recherche globale]
└── Résultats regroupés : Tickets / Actualités / Contacts

Espace copropriétaire
├── Mes lots
│   ├── Caractéristiques du lot
│   ├── Historique des interventions
│   └── Exporter mon lot  ← archive ZIP : tickets + vigiks (EF-WEB-112)
└── Mes contacts utiles
    ├── Syndic
    └── Conseil syndical

Tickets
├── Créer un ticket (panne, nuisance, question, urgence, bug)
├── Mes tickets en cours (filtres : Tous / Ouvert / En cours)
└── Historique — accordéon par année décroissante (3 ans max), toujours visible

Communication de la résidence
├── Actualités
│   └── Annonces, alertes, travaux, coupures
├── Calendrier de la résidence  ← NEW (EF-WEB-033)
│   └── Travaux, coupures, AG, maintenances — vue mensuelle + agenda
└── Communauté
    ├── Sondages
    ├── Boîte à idées
    └── Petites annonces  ← NEW (EF-WEB-116)
        └── Vente, don, recherche entre résidents

Accès & badges
└── Vigiks & télécommandes
    ├── Mes vigiks actifs
    ├── Mes télécommandes de parking
    ├── Demande de nouveau badge / télécommande
    ├── Signaler un badge perdu
    ├── Lien rapide prix badges → FAQ `/faq#badge-prix`
    └── Vue par locataire (bailleur)  ← NEW (EF-WEB-124)
        └── Accès actifs des locataires du bailleur (lecture seule)

Espace bailleur  ← NEW — ACCÈS RÉSERVÉ rôle copropriétaire bailleur
├── Mes Lots  (EF-WEB-120)
│   ├── Liste des lots possédés avec statut d'occupation
│   ├── Créer un bail  (EF-WEB-121, EF-WEB-122)
│   │   ├── Recherche de locataire (email exact / nom partiel)
│   │   └── Sélection multi-lots pour bail groupé
│   ├── Terminer un bail
│   └── Remise d'objets  (EF-WEB-123)
│       └── Clés, télécommandes, vigiks remis au locataire
└── Historique des baux terminés

Transparence & gouvernance
├── Décisions collectives
│   └── Votes, résolutions adoptées, règles en vigueur
├── Règlement de copropriété
│   └── Version à jour, annexes
└── État de la résidence
    └── Satisfaction, incidents résolus, projets en cours

Services pratiques
├── Annuaire
│   └── Copropriétaires, conseil syndical, contacts utiles
├── Prestataires
│   └── Intervenants autorisés, horaires, consignes d'accès
├── Plan de la résidence
│   └── Plans interactifs, localisation des équipements
└── FAQ
    └── Règles de vie, procédures, consignes déchets, stationnement

Espace conseil syndical  ← ACCÈS RÉSERVÉ rôle conseil_syndical + admin
├── Tableau de bord CS  (EF-WEB-110)
│   ├── KPIs : tickets ouverts, tickets > 7 j, vigiks en attente, comptes à valider
│   └── Prochains événements calendrier
├── Tickets CS
│   ├── Tous les tickets de la résidence
│   ├── Affichage demandeur + bâtiment
│   ├── Changement d'état + commentaires
│   └── Historique — accordéon par année (même comportement que la vue résident)
├── Validation en masse
│   ├── Demandes de vigiks en attente
│   └── Comptes résidents en attente d'activation
├── Statistiques opérationnelles  (EF-WEB-114 — phase 2)
│   └── Délais, volumes, taux de résolution
└── Paramétrage  ← ACCÈS RÉSERVÉ admin uniquement
    ├── Fiche copropriété  (EF-WEB-014)
    │   ├── Informations générales (immatriculation, année de construction…)
    │   ├── Assurance immeuble
    │   └── Carnet d'entretien (contrats de maintenance)    ├── Pages  (EF-WEB-115)  ← NEW
    │   └── Pour chaque page : titre, icône Lucide, sous-titre (éditeur riche TipTap)    ├── Sauvegardes  (EF-WEB-015)
    │   ├── Configuration (fréquence, nombre de versions, heure)
    │   ├── Sauvegarder maintenant
    │   └── Historique (téléchargement, restauration)
    ├── Télémétrie
    │   ├── KPI du jour (vues, utilisateurs uniques, pages)
    │   ├── Top pages 30 jours (classement, %)
    │   ├── Graphe 30 jours (barres jour par jour)
    │   ├── Historique mensuel (barres mois par mois)
    │   ├── Utilisateurs les plus actifs (top 30)
    │   └── Agréger maintenant (déclenchement manuel)
    ├── Profils d'accès documentaires  (EF-WEB-013)
    ├── Catégories de documents  (EF-WEB-013)
    └── Templates d’emails  (EF-WEB-073)
        ├── Comptes & invitations
        ├── Tickets & urgences
        ├── Vigiks & accès
        ├── Calendrier & événements
        └── Digest

Espace syndic  ← ACCÈS RÉSERVÉ rôle syndic
└── Rapports  (EF-WEB-113)
    ├── Rapport tickets (PDF / XLSX)
    ├── Liste des lots (PDF / XLSX)
    └── PV et résolutions AG

Note — Interface mandataire :
  Un mandataire ne voit que les sections relatives à son lot mandaté.
  Toutes les autres sections de la résidence sont masquées de sa navigation.
  Toute action hors périmètre affiche un message explicatif (principe UX-10).

Paramètres & personnalisation
├── Notifications
│   └── Préférences digest (quotidien / hebdomadaire)  ← NEW
├── Profil
│   └── Revoir le guide d'accueil  ← NEW
├── Accessibilité / Langue
└── À propos / Licences open source

Pied de page (toutes les pages)
├── Mentions légales  ← LCEN Art. 6, accessible sans connexion
└── Politique de confidentialité  ← RGPD Art. 13, accessible sans connexion
```

## Matrice des droits par rôle

> **Locataire** : mêmes droits de consultation que copropriétaire résident — ne peut pas être admin ni membre du conseil syndical.
> **Bailleur** : accès complet à l'espace bailleur (gestion locative, baux, remise d'objets). Voir ses locataires dans Accès & Badges.
> **Syndic** : accès en **lecture seule** sur toute l'application (pas de création ni modification). Reçoit les notifications d'urgence indépendamment de ce rôle.
> **Mandataire** : lecture seule limitée à son lot uniquement — navigation réduite (cf. note arborescence).
> **Prestataire** : aucun accès à l'application.

### Règles de filtrage contenu (implémentées dans `api/app/utils/visibility.py`)

- **Périmètre géographique** : `résidence / parking / cave / aful` = visible par tous les résidents ; `bat:N` = visible uniquement par le résident du bâtiment N. CS/Admin voient tout.
- **public_cible (publications)** : `résidents` = tous les résidents actifs ; `copropriétaires` = statut `copropriétaire_*` uniquement ; `locataires` = statut `locataire` uniquement ; `conseil_syndical` = CS et Admin uniquement. Logique opt-in : si aucune valeur de `public_cible` ne correspond au profil, la publication est masquée.
- **AG (événements)** : visible uniquement par les propriétaires, CS et admins. Masqué pour locataires, résidents simples, mandataires, syndics.
- **maintenance_recurrente (événements)** : masqué pour tous (usage interne planificateur uniquement).
- **Sondages** : `profils_autorises` (CSV de StatutUtilisateur) + `batiments_ids` (CSV d'ids). Vide = sans restriction. CS/Admin voient tout.
- **Tickets** : chaque résident (tout rôle < CS) ne voit que ses propres tickets et messages publics. Les messages internes sont réservés au CS/Admin.

| Section | Résident / Locataire | Conseil syndical | Syndic | Mandataire | Admin |
|---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---|-|---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---|--|---|---|---|---|---|---||---|---|---|---|---|---|--|---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---|-|
| Mon lot / Mes documents | ✅ propres données | ✅ tous | 👁 lecture | 👁 son lot | ✅ |
| Export par lot | ✅ son lot uniquement | ✅ tous lots | ❌ | 👁 son lot en lecture | ✅ |
| Tickets | ✅ créer + voir les siennes | ✅ toutes | 👁 lecture | 👁 son lot | ✅ |
| Communication (actualités, sondages…) | 👁 lecture | ✅ écriture | 👁 lecture | ❌ | ✅ |
| Petites annonces | ✅ CRUD propres | ✅ CRUD + modération | 👁 lecture | ❌ | ✅ |
| Calendrier résidence | 👁 lecture | ✅ écriture | 👁 lecture | ❌ | ✅ |
| Accès & badges | ✅ propres badges | ✅ toutes | 👁 lecture | ❌ | ✅ |
| Transparence & gouvernance | 👁 lecture | ✅ écriture | 👁 lecture | ❌ | ✅ |
| Annuaire / Prestataires | 👁 lecture | ✅ écriture | 👁 lecture | ❌ | ✅ |
| Fiche copropriété (lecture) | 👁 lecture | 👁 lecture | 👁 complet | ❌ | ✅ |
| Fiche copropriété (édition) | ❌ | ❌ | ❌ | ❌ | ✅ |
| Sauvegardes (configuration + restauration) | ❌ | ❌ | ❌ | ❌ | ✅ |
| Recherche globale | ✅ périmètre réduit | ✅ périmètre complet | 👁 lecture | 👁 son lot | ✅ |
| Espace CS (tableau de bord, validation, stats) | ❌ | ✅ | ❌ | ❌ | ✅ |
| Espace bailleur (baux, remise objets) | ❌ bailleur : ✅ | ❌ | ❌ | ❌ | ✅ |
| Vue accès par locataire | ❌ bailleur : 👁 | ❌ | ❌ | ❌ | ✅ |
| Paramétrage documentaire (profils, catégories) | ❌ | ❌ | ❌ | ❌ | ✅ |
| Espace syndic (rapports) | ❌ | ❌ | ✅ export uniquement | ❌ | ✅ |
| Paramètres profil | ✅ son profil | ✅ son profil | ✅ son profil | ✅ son profil | ✅ |
| Administration (gestion comptes, imports) | ❌ | partiel | ❌ | ❌ | ✅ |

|---|---|---|---|---|---|

## Spec UX — Cohérence des menus et titres dynamiques (à valider avant implémentation)

> **Contexte.** La mise à jour dynamique des libellés et icônes n'est pas uniforme entre la sidebar desktop, l'overlay hamburger mobile et les titres de page. Cette section définit, pour chacune des trois visions, le comportement attendu et les valeurs par défaut, afin d'être validée avant tout correctif du code.

|---|---|---|---|---|---|

### Principes généraux

1. **Source unique de vérité** : toute valeur configurable est lue depuis le store réactif `configStore` (alimenté par `GET /api/config`), jamais depuis `localStorage` directement.
2. **Fallback garanti** : si aucune valeur personnalisée n'est enregistrée, les valeurs par défaut du tableau ci-dessous s'appliquent.
3. **Uniformité** : sidebar PC et overlay hamburger affichent exactement les mêmes libellés, icônes et ordre — il ne doit pas y avoir de divergence entre les deux vues.
4. **Champ `icone` à ajouter** : le modèle `PageDef` ne contient pas encore de champ `icone`. Il doit être ajouté pour rendre l'icône de chaque entrée de menu configurable depuis Admin → Descriptif des pages.
5. **Ordre paramétrable** : l'ordre des entrées de menu est modifiable dans Admin → Descriptif des pages (déjà partiellement implémenté via `movePage`), mais doit être persisté en base (clé `pages_order`) et non uniquement dans `localStorage`.

|---|---|---|---|---|---|

### Tableau des valeurs par défaut et de personnalisation

#### Légende des colonnes

| Colonne | Signification |
|---|---|---|---|---|---||---|---|---|---|---|---||
| **Clé de config** | Clé stockée dans `config` (table `configuration` côté API) |
| **Valeur par défaut** | Ce qui s'affiche sans aucune personnalisation admin |
| **Vision PC — Menu** | Icône + libellé affiché dans la sidebar fixe (≥ 768 px) |
| **Vision PC — Titre page** | Icône + H1 affiché en haut du contenu de la page |
| **Vision Hamburger — Menu** | Icône + libellé affiché dans l'overlay mobile (≤ 767 px) |
| **Vision Hamburger — Titre page** | Identique à Vision PC (même composant de titre) |

|---|---|---|---|---|---|

#### A. Éléments globaux de l'application

| Élément | Clé de config | Valeur par défaut | Vision PC | Vision Hamburger |
|---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||
| **Icône de l'application** (brand) | `site_icone` *(à créer)* | `building-2` (Lucide monochrome) | Affiché en haut de la sidebar, à gauche du nom | Affiché dans la topbar, à gauche du nom |
| **Nom de l'application** (brand) | `site_nom` | `5Hostachy` | Texte à droite de l'icône dans la sidebar | Texte à droite de l'icône dans la topbar |
| **URL publique** | `site_url` | `https://<your-domain>/` | Utilisé dans le pied de page (lien cliquable) | Idem |
| **Icône page de connexion** | `login_icone` *(à créer)* | `building-2` (Lucide) | Affiché centré en haut de la carte de connexion | Idem (pas de sidebar/hamburger sur la page auth) |
| **Titre page de connexion** | *(réutilise `site_nom`)* | Valeur de `site_nom` — ex. `5Hostachy` | H1 de la carte de connexion = nom de l'application | Idem |
| **Sous-titre page de connexion** | `login_sous_titre` | `Votre espace numérique de résidence` | Ligne de sous-titre sous le H1, vide si non renseigné | Idem |

|---|---|---|---|---|---|

#### B. Entrées du menu de navigation (ordre par défaut)

> Le champ `icone` est à ajouter au modèle `PageDef` dans Admin → Descriptif des pages.  
> L'ordre ci-dessous est l'ordre par défaut ; il est modifiable dans Admin.

| Ordre | Page | Clé config | Label menu défaut | Titre page défaut | Descriptif défaut |
|---|---|---|---|---|---|
| 1 | Tableau de bord | `page_config_tableau-de-bord` | Accueil | Tableau de bord | Votre espace numérique de résidence : actualités, demandes, accès et gouvernance de votre copropriété en un seul endroit, avec événements récents incluant les prestations ponctuelles non terminées. |
| 2 | Actualités | `page_config_actualites` | Actualités | Actualités | Publications officielles du conseil syndical : informations importantes, travaux et actualités de la résidence. |
| 3 | Calendrier | `page_config_calendrier` | Calendrier | Calendrier | Pilotage des événements de la résidence via trois vues complémentaires : Liste (chronologique), Kanban (avancement), Archives (historique). |
| 4 | Tickets | `page_config_mes-demandes` | Tickets | Mes Tickets | Signalez un problème, une nuisance ou posez une question au conseil syndical. Suivez l'avancement de vos tickets. |
| 5 | Annuaire | `page_config_annuaire` | Annuaire | Annuaire | Coordonnées des membres du Conseil Syndical et du Syndic. |
| 6 | Résidence | `page_config_residence` | Résidence | Ma résidence | Documents et informations de la copropriété. |
| 7 | Mon lot | `page_config_mon-lot` | Mes lots | Mes lots | Informations sur votre bien : situation de vous lots (appartement, cave & parkings) dans la résidence et gestion locative pour le copropriétaire bailleur. |
| 8 | Accès & badges | `page_config_acces-badges` | Accès & badges | Accès & badges | Gestion de vos Télécommandes parkings & Vigiks. |
| 9 | Prestataires *(proprio/CS)* | `page_config_prestataires` | Prestataires | Prestataires | Intervenants de la résidence, contrats de maintenance, documents contractuels et creation de prestations avec workflow, planning et pieces jointes. |
| 10 | Communauté | `page_config_communaute` | Communauté | Communauté | Sondages et boîte à idées pour contribuer à la vie de la résidence. |
| 11 | FAQ | `page_config_faq` | FAQ | FAQ | Réponses aux questions fréquentes sur la vie en résidence, les services et la réglementation de la copropriété, avec liens contextuels vers les actions clés (ex : Accès & badges). |
| 12 | Espace CS *(CS uniquement)* | `page_config_espace-cs` | Espace CS | Espace CS | Tableau de bord CS : validation des utilisateurs, tickets de la résidence, demandes d'accès — réservé au Conseil Syndical. |
| 13 | Paramétrage *(admin uniquement)* | `page_config_admin` | Admin | Paramétrage | Administration de la plateforme : comptes, utilisateurs, rôles, modèles e-mail, paramétrage et référentiels — réservé aux admins. |
| — | Profil *(pied de nav, non réordonnable)* | `page_config_profil` | Prénom de l'utilisateur connecté | Mon profil | Vos informations personnelles (mot de passe, lots...), sécurité du compte et matrice de préférences de notifications (appli / e-mail). |
| — | Déconnexion *(pied de nav, non configurable)* | — | Se déconnecter | — | — |

#### C. Comportement par vision

| Élément | Vision PC (sidebar ≥ 768 px) | Vision Hamburger (≤ 767 px) |
|---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||
| **Brand (icône + nom app)** | Affiché en haut de la sidebar fixe gauche, lien vers `/tableau-de-bord` | Affiché dans la topbar fixe en haut, lien vers `/tableau-de-bord` |
| **Icône menu** | Icône Lucide monochrome (SVG inline, `currentColor`, 20 px), affiché avant le label | Idem dans l'overlay plein écran (22 px) |
| **Label menu** | `navLabel` configuré ou valeur par défaut du tableau B | Identique — même source, même valeur |
| **Ordre des entrées** | Ordre issu de `pages_order` (config API) | Identique |
| **Titre de page (H1)** | `icone` + `titre` configuré, affiché en haut du contenu | Identique (même composant) |
| **Onglet navigateur `<title>`** | `{titre} — {site_nom}` | Identique |
| **Entrée active** | Surbrillance de l'item courant (fond coloré) | Idem dans l'overlay |
| **Profil connecté** | Pied de sidebar : icône 👤 + prénom | Pied de l'overlay : icône 👤 + prénom |
| **Déconnexion** | Pied de sidebar : icône 🚪 + « Se déconnecter » | Pied de l'overlay : icône 🚪 + « Se déconnecter » |

|---|---|---|---|---|---|

#### D. Pied de page (footer)

Le pied de page est affiché sur toutes les pages de l'application (hors auth).
Il se règle dans **Admin › Site › Pied de page** (08/10/2026).

**Ce qui fait foi : le code, pas cette section.** Les éléments, leur ordre et
ceux qui ne se masquent pas sont déclarés dans `front/src/lib/piedDePage.ts`
(`ELEMENTS_PIED`) ; le rendu, unique pour le site et l'aperçu de
l'administration, est `front/src/lib/components/PiedDePage.svelte`. Cette
section décrivait un format (`v{version}+{hash}.{date}`) et trois clés « à
créer » qui n'existaient plus, ou pas encore.

**Rendu par défaut :**

```
© 2026 · {site_nom} · v2.118.1 · RPi1 · CoproFirst · Mentions légales · Politique de confidentialité
```

- La clé `pied_de_page_masques` (publique, liste de codes) porte les éléments
  **retirés**. Si elle est absente, tout s'affiche, y compris un élément ajouté plus tard.
- **Masquables** : année, nom de la résidence (lien vers `site_url`), texte
  libre, version, serveur (`VITE_INSTANCE_ID`, absent sur le poste de développement).
- **L'année** : `pied_de_page_annee_debut` (publique) est l'année de création —
  « © 2026 » cette année-là, « © 2026–2027 » ensuite ; vide, l'année en cours seule.
- **Le texte libre** : `pied_de_page_texte` (publique, une ligne, 120 caractères,
  bornée aussi par le serveur). Vide, il ne s'affiche pas.
- **L'ordre** : `pied_de_page_ordre` (publique, liste de codes) porte l'ordre de TOUS
  les éléments, verrouillés compris — ils se déplacent, ils ne se masquent pas ;
  un élément absent de la valeur se range en fin. Le réglage le change avec ↑ ↓.
- **Le préfixe du nom** : `pied_de_page_prefixe_nom` (publique, 40 caractères) s'écrit
  devant le nom, sans séparateur (« Résidence 5Hostachy ») ; `site_nom` ne change pas.
- **Verrouillés** : le lien vers le code source de la version en service
  (AGPLv3 §13), les mentions légales (LCEN, art. 6) et la politique de
  confidentialité (RGPD, art. 13). `lireMasques` les écarte quelle que soit la valeur en base.
- La version s'affiche **courte**. L'empreinte et la date du build sont dans
  l'infobulle. Le post-check P3 lit la version dans le bundle, jamais dans ce rendu.

🔒 `front/e2e/pied-de-page.spec.ts`.

### Règles UX — Interactions patrons

#### Zones expansables (accordions, items FAQ, cartes cliquables)

| Règle | Détail |
|---|---|---|---|---|---||---|---|---|---|---|---||
| **Zone de clic** | Toute la ligne d'en-tête (DIV ou HEADER), pas uniquement le texte du titre, déclenche l'expansion/réduction |
| **`user-select: none`** | Appliqué sur les éléments `<button>` titre pour éviter la sélection de texte au double-clic |
| **Propagation** | Les boutons d'action internes (édition, suppression, masquage) utilisent `on:click|stopPropagation` pour ne pas déclencher le toggle |
| **Contenu expansé** | Le contenu expansé utilise `on:click|stopPropagation` pour ne pas fermer quand l'utilisateur lit ou sélectionne du texte |
| **Accordions exclusifs** | Admin → Paramétrage : sections **Pages** et **Référentiels** — ouvrir une entrée ferme la précédente |
| **Accordéon Historique Tickets** | Section en bas de page Tickets. Niveau 1 : toggle « Historique ». Niveau 2 : une entrée par année (décroissant, 3 ans max) avec le décompte de tickets. Visible pour tous les profils (copro, CS, admin), même sans tickets actifs. |
| **Accessibilité** | `role="button"`, `tabindex="0"`, `on:keydown` (Enter/Espace) sur les `<div>` cliquables non natifs |


#### Règle de prévisualisation dans les cards repliées

| Condition | Comportement |
|---|---|---|---|---|---||---|---|---|---|---|---||
| Liste de **≤ 7 entrées** | La card repliée affiche un **aperçu de 5 lignes** du contenu (`.clamp-5`) |
| Liste de **> 7 entrées** | La card repliée affiche **uniquement le titre** (en-tête de la card) — aucun aperçu de contenu |

Cette règle s'applique à toutes les listes de cards expansibles :

| Page | Variable de contrôle | Contenu masqué quand >7 items + replié |
|---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||
| **FAQ** | `catItems.length > 7` (par catégorie) | Aperçu de la réponse (`.faq-a.clamp-5`) |
| **Actualités** | `pubList.length > 7` | Aperçu du contenu (`pub-preview.clamp-5`) |
| **Tableau de bord** — pubs | `pubList.length > 7` | Aperçu contenu pub (`pub-contenu.clamp-5`) |
| **Tableau de bord** — évènements | `evenementList.length > 7` | Aperçu description évènement (`ev-preview.clamp-5`) |
| **Prestataires** | `filteredPrests.length > 7` | Contacts (téléphone, e-mail) + badges (nb contrats, prochaine visite) |

> **Note** : les boutons d'action (éditer, supprimer) et la flèche de toggle restent toujours visibles quel que soit le mode.
#### Badge « Épinglé »

| Comportement | Implémentation |
|---|---|---|---|---|---||---|---|---|---|---|---||
| **Position** | Superposé sur le bord supérieur de la carte : `position: absolute; top: -10px; left: 12px` |
| **Conteneur** | La carte parent : `position: relative; overflow: visible` |
| **Style** | Fond `var(--color-primary)`, texte blanc, `border-radius: 10px`, petite police |
| **Flux** | Le badge flotte à cheval sur le cadre — ne prend pas de ligne dans le flux de la carte |

#### Icône Lucide devant le titre H1

| Comportement | Détail |
|---|---|---|---|---|---||---|---|---|---|---|---||
| **Source** | Champ `icone` de `PageDef` — même icône que le menu, configurable dans Admin → Paramétrage |
| **Rendu** | `<h1 style="display:flex;align-items:center;gap:.4rem"><Icon name={_pc.icone} size={20} />{_pc.titre}</h1>` |
| **Fallback** | Si `icone` non défini : icône par défaut codée dans la page (ex. `'newspaper'` pour Actualités) |
| **Exception** | Page **Tableau de bord** : H1 personnalisé (message de bienvenue) — sans icône Lucide |
### Écarts actuels à corriger (diagnostic)

| # | Problème constaté | Impact |
|---|---|---|---|---|---||---|---|---|---|---|---||---|---|---|---|---|---||
| 1 | `getNavLabel()` dans `Nav.svelte` lit `localStorage` directement, pas le store réactif `configStore` | Les labels menu ne se mettent pas à jour en temps réel après un changement admin sans rechargement de page |
| 2 | Le champ `icone` n'existe pas dans `PageDef` — les icônes des entrées de menu sont codées en dur dans des tableaux JS | L'icône n'est pas personnalisable depuis l'interface admin |
| 3 | `pages_order` est stocké dans `localStorage` uniquement — non synchronisé entre appareils et perdu à l'effacement du cache | L'ordre de menu n'est pas cohérent d'un navigateur à l'autre |
| ~~4~~ | ~~La page de connexion a un sous-titre codé en dur~~ | ✅ **Corrigé (commit 63ff968)** — `login_sous_titre` lu depuis `configStore`, valeur par défaut `Votre espace numérique de résidence`, éditable dans Admin → Paramètres généraux |
| ~~5~~ | ~~Le footer — pas de lien sur le nom, format version incorrect~~ | ✅ **Corrigé (commit 63ff968)** — nom toujours lié (`site_url` + fallback), format `v{version}+{hash}.{date}` |
| 6 | Toutes les pages n'implémentent pas `<svelte:head><title>` avec `{_pc.titre} — {_siteNom}` | Onglet navigateur incohérent selon les pages |
| 7 | L'icône de l'application (`site_icone`) et l'icône de la page de connexion (`login_icone`) ne sont pas configurables | Impossible d'adapter le branding sans toucher au code |

|---|---|---|---|---|---|

### Parcours de validation

> Avant tout correctif, valider les points suivants :
>
> - [ ] **A** — Les valeurs par défaut du tableau B sont-elles correctes (icônes, labels, titres) ?
> - [x] **B** — Icônes du menu : **icônes Lucide monochrome** (`currentColor`, SVG outline). Les emojis restent uniquement pour les boutons d'action dans les tableaux (conforme à la charte graphique existante). La palette finale est définie dans `docs/icones-menu.md`.
> - [ ] **C** — L'ordre des menus doit-il être persisté en base ou en `localStorage` suffit-il ?
> - [x] **D** — Format footer validé et implémenté : `v{version}+{hash}.{date build}` — séparateur `.`, nom toujours lié (commit 63ff968).
> - [x] **E** — `login_sous_titre` intégré dans la section **Paramètres généraux** existante (Admin → Paramètres généraux). Les champs `login_icone` et `site_icone` restent à créer dans cette même section.


