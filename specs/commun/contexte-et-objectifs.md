# Contexte et objectifs

## Contexte

La **Résidence du Parc** est une copropriété située au 5 boulevard Fernand Hostachy, 78290 Croissy-sur-Seine. Elle est composée de 4 bâtiments (RDC + 3 étages + sous-sols), gérée par un syndic professionnel et un conseil syndical élu.

5Hostachy est l'extranet numérique privé de la résidence. Il remplace les échanges papier/email non structurés entre résidents, conseil syndical et syndic, et constitue l'outil de gestion quotidienne de la copropriété.

## Objectifs

- Permettre aux résidents de consulter leurs informations de lot, documents, et de soumettre des demandes (tickets, vigiks, télécommandes).
- Donner au conseil syndical un outil de communication, de suivi des demandes et de gestion des accès.
- Offrir au syndic un accès lecture seule à toutes les données de la copropriété.
- Auto-hébergé sur Raspberry Pi 5 dans la résidence — souveraineté totale des données.

## Périmètre

### Dans le périmètre

- Gestion des résidents (comptes, rôles, lots)
- Tickets et demandes (pannes, nuisances, urgences, vigiks)
- Documents (PV d'AG, règlement, plans, diagnostics, attestations) — accessibles via les prestataires et contrats d'entretien (usage CS/admin)
- Communication (actualités, sondages, boîte à idées)
- Accès & sécurité (badges, télécommandes)
- PWA mobile (iOS/Android)

### Hors périmètre

- Gestion comptable et appels de charges (outil syndic dédié)
- Tenue des assemblées générales (outil tiers ou présentiel)
- Application native Android (Play Store) — l'application **iOS** native, elle, entre dans le périmètre le 01/11/2026 : [architecture/stack.md § Application mobile](../architecture/stack.md#application-mobile) (#2460)

---

## Cadre légal applicable

> Ce tableau recense l'ensemble des obligations légales françaises et européennes impactant l'application. Chaque item renvoie aux exigences fonctionnelles (EF) ou non-fonctionnelles (ENF) correspondantes.

### Obligations directement impactantes

| Texte | Domaine | Obligations principales pour 5Hostachy | Exigences |
|---|---|---|---|
| **RGPD** (UE 2016/679) + **Loi Informatique et Libertés** (Loi 78-17 modifiée) | Protection des données | Consentement éclairé à l'inscription, droits des personnes (accès, rectification, effacement, portabilité…), registre des traitements, notification CNIL sous 72 h, blocage < 15 ans | EF-WEB-001, EF-WEB-090 à 092, EF-MOB-060 à 062 |
| **LCEN** (Loi n° 2004-575 du 21 juin 2004) Art. 6 | Économie numérique | **Mentions légales obligatoires** sur tout service de communication en ligne : identité de l'éditeur (le syndicat des copropriétaires), directeur de publication (président du CS), coordonnées de l'hébergeur. S'applique même à un extranet privé. | EF-WEB-100 |
| **LCEN + CPCE Art. L33-4-1** | Anti-spam | Tout email envoyé par l'application doit : identifier clairement l'expéditeur, proposer un lien de désinscription pour les communications non essentielles, respecter le consentement opt-in préalable pour les communications commerciales/d'information | EF-WEB-101, EF-WEB-072 |
| **Loi du 10 juillet 1965 + Décret du 17 mars 1967** | Copropriété | Conservation des PV d'AG (10 ans minimum), tenue du registre des copropriétaires, carnet d'entretien de l'immeuble, fiche synthétique annuelle. L'application constitue le support numérique de ces obligations documentaires. | EF-WEB-012, EF-WEB-050 |
| **Loi ALUR (2014) + Loi ELAN (2018) + Ordonnance 2019-1101** | Copropriété numérique | Obligation d'un espace en ligne sécurisé pour les copropriétés : accès aux PV, documents, et informations par lot. **5Hostachy est l'extranet légal de la résidence** au sens de l'Art. 18-2 de la Loi 1965 modifiée. | EF-WEB-012, EF-WEB-050 |

### Obligations conditionnelles (selon fonctionnalités activées)

| Texte | Condition d'application | Obligations | Exigences |
|---|---|---|---|
| **eIDAS** (Règlement UE 910/2014) + **Ordonnance 2016-131** | Si vote dématérialisé d'AG ou résolutions signées électroniquement | La décision doit avoir valeur probatoire : signature électronique qualifiée (niveau eIDAS 3) ou au minimum avancée (niveau 2) pour les résolutions importantes. Les sondages internes n'y sont pas soumis. | EF-WEB-031 (note) |
| **Directive NIS2** (UE 2022/2555) — transposée Loi 2023-703 | Auto-hébergement sur RPi accessible depuis l'extérieur | Mesures de cybersécurité adaptées au risque, procédure de notification des incidents, cloisonnement réseau, mises à jour de sécurité. L'ANSSI recommande le référentiel SecNumCloud pour les services sensibles. | ENF Sécurité |
| **DSP2 / PSD2** (Directive UE 2015/2366) | Si paiement en ligne des charges ou prestations | Authentification forte du client (SCA), agrément prestataire de services de paiement. **Hors périmètre MVP** — à considérer si l'app intègre un module de paiement. | Hors périmètre |
| **Loi pour une République Numérique** (Loi n° 2016-1321) + **RGAA 4.1** | Recommandé pour tout service numérique | RGAA 4.1 est obligatoire pour les organismes publics ; fortement recommandé pour le secteur privé. Le niveau WCAG 2.2 AA ciblé couvre l'essentiel du RGAA 4.1. | ENF Accessibilité |

### Bonnes pratiques réglementaires (non obligatoires mais recommandées)

| Texte / Référentiel | Recommandation |
|---|---|
| **ANSSI — Recommandations relatives à l'authentification multifacteur** (CERTFR-2021-AVI) | MFA optionnel pour les membres du conseil syndical et l'admin |
| **ANSSI — Guide d'hygiène informatique** | Mises à jour automatiques (Watchtower), sauvegardes testées, cloisonnement réseau |
| **CNIL — Recommandation cookies et traceurs** | Pas de bandeau cookie si aucun cookie non essentiel n'est déposé (ce qui est le cas par défaut avec l'architecture choisie) |
| **Référentiel général d'écoconception des services numériques (RGESN)** | Éco-conception déjà prise en compte dans les choix techniques (bundle < 150 Ko, pas de framework CSS lourd, pas de tracker) |
