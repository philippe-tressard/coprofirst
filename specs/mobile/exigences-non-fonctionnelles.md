# Exigences non fonctionnelles — Application mobile (PWA)

---

## Performance

- First Contentful Paint (FCP) < 2 s sur réseau 4G.
- Time to Interactive (TTI) < 3 s.
- Taille du bundle JS < 150 Ko gzippé.
- Lazy-loading des images et des sections hors-écran.
- Service worker Workbox : mise en cache des assets statiques et des données essentielles pour le fonctionnement hors-ligne partiel.
- Score Lighthouse PWA ≥ 90 (performance, accessibilité, best practices).

---

## Accessibilité

- Niveau visé : **WCAG 2.2 AA**.
- Toutes les zones interactives : taille minimale 44 × 44 px (Apple HIG / Material Design).
- Contraste ≥ 4,5:1 sur tous les écrans.
- Support du lecteur d'écran natif (VoiceOver iOS, TalkBack Android).
- Navigation sans gestes complexes : chaque action réalisable en tap simple ou double tap.
- Respect de `prefers-reduced-motion` et `prefers-color-scheme`.

---

## Compatibilité OS et versions

| Plateforme | Version minimale | Navigateur |
|------------|-----------------|------------|
| iOS | 16.4+ | Safari |
| Android | 10+ (API 29+) | Chrome 120+ |

- Installation A2HS (Add to Home Screen) supportée sur les deux plateformes.
- Notifications push PWA supportées : iOS 16.4+ (Safari), Android (Chrome).
- Ces exigences sont celles de la PWA. Une application iOS native s'y ajoute depuis le 01/11/2026 (App Store ; Play Store hors périmètre) : [architecture/stack.md § Application mobile](../architecture/stack.md#application-mobile).

---

## Sécurité

- Toutes les communications via HTTPS (TLS 1.2+).
- Tokens JWT en cookies `HttpOnly` + `Secure` + `SameSite=Strict`.
- Pas de données sensibles dans `localStorage` ni dans les URLs.
- Verrouillage de session après 5 tentatives de connexion échouées (15 min).
- Les données en cache (Workbox) ne contiennent pas de mots de passe ni de tokens.

---

## Hors-ligne / connectivité

| Fonctionnalité | Disponible hors-ligne |
|----------------|-----------------------|
| Tableau de bord (données en cache) | ✅ |
| Mon lot — informations de base | ✅ |
| Actualités (dernière version en cache) | ✅ |
| Consultation de documents (téléchargés) | ✅ |
| Création de ticket | ❌ (connexion requise) |
| Commande vigik / télécommande | ❌ (connexion requise) |
| Sondages et votes | ❌ (connexion requise) |

- Message clair affiché à l'utilisateur en cas de tentative d'action hors-ligne.
- Synchronisation automatique du cache à la reconnexion.

---

## Éco-conception

- Pas de framework CSS lourd, animations minimales.
- Images compressées (AVIF/WebP), chargées uniquement si nécessaire.
- Aucun tracker tiers, aucune collecte publicitaire.

---

## Conformité RGPD (Règlement UE 2016/679 + Loi Informatique et Libertés)

- Même socle que la version web (voir `web/exigences-non-fonctionnelles.md`).
- Les notifications push PWA requièrent un **double consentement** : consentement RGPD d'abord (finalité de traitement), puis permission système navigateur/OS — les deux sont indépendants et révocables séparément.
- L'export des données personnelles (droit à la portabilité, Art. 20 RGPD) est téléchargeable ou partageable via le Share Sheet natif iOS/Android.
- Les mentions légales RGPD du formulaire d'inscription respectent les contraintes d'accessibilité WCAG 2.2 AA (lisible sur 320 px, contraste ≥ 4,5:1).
- Les mineurs de moins de **15 ans** sont bloqués à l'inscription (Art. 8 RGPD + Loi n° 2018-493 du 20 juin 2018).
- Les exigences fonctionnelles associées sont EF-MOB-060, EF-MOB-061, EF-MOB-062.

---

## Autres conformités légales (LCEN, ALUR/ELAN, NIS2)

- Les obligations **LCEN** (mentions légales, anti-spam) et **ALUR/ELAN** (extranet copropriété) s'appliquent à l'ensemble de l'application (web + mobile PWA) — voir `web/exigences-non-fonctionnelles.md` pour le détail.
- Les recommandations **NIS2 / ANSSI** (mises à jour, sauvegardes, cloisonnement réseau, journalisation) s'appliquent à l'infrastructure hébergeant la PWA — voir `web/exigences-non-fonctionnelles.md`.
- Les communications push respectent les obligations anti-spam : les notifications non essentielles ne sont envoyées qu'avec consentement opt-in révocable (LCEN + CPCE Art. L33-4-1).

---

## Conformité juridique — Licences open source

- Toute dépendance tierce (npm, PyPI) doit être licenciée sous une licence compatible avec un usage commercial : MIT, Apache 2.0, BSD, ISC. Les licences copyleft fortes (GPL, AGPL) sont interdites sans validation explicite.
- Un inventaire des licences est généré automatiquement à chaque build de production (outil : `license-checker` côté front, `pip-licenses` côté API).
- L'application expose une page **À propos / Licences** accessible depuis le menu Profil, listant les bibliothèques utilisées avec leur nom, version, auteur et texte de licence.
- Les mentions de copyright imposées par les licences (ex. Apache 2.0 `NOTICE`, MIT copyright header) sont incluses dans cette page et dans le fichier `LICENSES.md` du dépôt.
- Aucune bibliothèque sans licence identifiée ne peut être intégrée en production.
