# Navigation et arborescence — Application mobile (PWA)

> ⚠️ **Arborescence d'origine, périmée** : des pages décrites ici ont été fusionnées ou retirées (Accès & badges, Transparence & gouvernance, publications, calendrier). Le [manuel utilisateur](../../docs/manuel-utilisateur.html) et `front/src/lib/pages.ts` font foi.

> Structure des écrans et navigation principale de la PWA mobile.  
> Sur mobile (≤ 767 px), la navigation s'organise autour d'un **menu hamburger** (topbar fixe en haut de l'écran) qui ouvre un overlay plein écran listant toutes les sections.  
> Sur desktop (≥ 768 px), la navigation reste une **sidebar latérale fixe** de 220 px.

## Arborescence

```
Authentification (hors-session)
├── Connexion
├── Création de compte (onboarding)
└── Récupération de mot de passe

Onboarding (première connexion uniquement)
├── Étape 1 — Compléter le profil  (skippable)
├── Étape 2 — Découvrir la résidence  (skippable)
├── Étape 3 — Activer les notifications  (skippable)
└── Étape 4 — Votre tableau de bord est prêt

════════════════════════════════════
MENU HAMBURGER (mobile) — SIDEBAR (desktop)
════════════════════════════════════

Mobile (≤ 767 px) :
  [Topbar fixe]
  🏢 5Hostachy                         ☰
  Clic sur ☰ → overlay plein écran scrollable avec tous les liens
  Fermeture : re-clic sur ✕, clic sur le fond, ou navigation vers une page

Desktop (≥ 768 px) : sidebar latérale 220 px (inchangée)
────────────────────────────────────
LINKS DISPONIBLES DANS LE MENU

[Accueil]
├── Tableau de bord : actualités, alertes, raccourcis
├── [barre de complétion de profil si < 100 %]
└── 🔴 Bouton urgence (accessible en 2 taps)

[Mon lot]
├── Caractéristiques du lot
├── Historique des interventions
├── Mes vigiks
├── Mes télécommandes de parking
├── Mes documents
│   ├── Attestations
│   ├── PV d'AG
│   ├── Règlement de copropriété
│   ├── Plans
│   └── Diagnostics
└── Exporter mon lot  ← archive ZIP (EF-MOB-066, phase 2)

[Tickets]
├── Créer un ticket
│   ├── Panne
│   ├── Nuisance
│   ├── Question
│   ├── 🔴 Urgence (inondation, panne majeure)
│   └── Bug
├── Mes tickets en cours (filtres : Tous / Ouvert / En cours)
└── Historique — accordéon par année décroissante (3 ans max), toujours visible

[Résidence]
├── Actualités et alertes
│   └── Travaux, coupures eau/électricité, annonces
├── Calendrier de la résidence  ← NEW (EF-MOB-064)
│   └── Vue semaine + vue agenda — coupures/urgences en rouge
├── Tableau d'affichage numérique
│   └── Messages conseil syndical, objets trouvés, petites annonces
├── Sondages
├── Boîte à idées
├── Accès & sécurité (badges)
├── Annuaire
├── Prestataires
├── Plan de la résidence
├── FAQ
└── [Espace CS]  ← visible uniquement pour conseil_syndical + admin
    ├── Tableau de bord CS (KPIs)
    └── Validation en masse (vigiks, comptes)

[𝄱 Recherche]  ← icône loupe dans la barre de navigation supérieure
└── Modale plein écran — résultats : Tickets / Documents / Actualités / Contacts

[Profil]
├── Mes informations personnelles
├── Mes contacts utiles (syndic, conseil syndical)
├── Notifications
│   └── Préférences digest (quotidien / hebdomadaire)  ← NEW
├── Revoir le guide d'accueil  ← NEW (relancer l'onboarding)
├── Accessibilité / Langue
├── À propos / Licences open source
├── Mentions légales  ← LCEN Art. 6, accessible sans connexion
└── Déconnexion

Note — Interface mandataire :
  L'onglet [Résidence] n'affiche que le calendrier et les actualités générales.
  L'onglet [Mon lot] est limité au lot mandaté.
  Toute action hors périmètre affiche un message explicatif (principe UX-10).
```

## Gestes et navigation mobile

- **Swipe retour** : navigation arrière native (iOS et Android).
- **Pull to refresh** : actualisation des listes (actualités, tickets).
- **Navigation modale** : création de ticket, commande de vigik/télécommande.
- **Notifications push** : badge sur l'onglet concerné (Demandes, Résidence).

## Fonctionnement hors-ligne

| Écran | Disponible hors-ligne |
|-------|-----------------------|
| Tableau de bord (cache) | ✅ |
| Mon lot (données de base) | ✅ |
| Actualités (cache) | ✅ (dernière version) |
| Calendrier résidence (cache) | ✅ (dernière version synchronisée) |
| Résultats de recherche | ❌ (requiert connexion) |
| Création de ticket | ❌ (requiert connexion) |
| Commande vigik/télécommande | ❌ (requiert connexion) |
| Export par lot | ❌ (requiert connexion) |
