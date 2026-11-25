# Principes UX

> 1. Responsive Design

Utiliser une approche mobile-first.
Employer des grilles flexibles (Flexbox / CSS Grid).
Utiliser des unités relatives (rem, %, vw/vh).
Générer des images responsives (srcset, sizes).
Intégrer des médias-queries modernes (prefers-color-scheme, prefers-reduced-motion).

**Breakpoints définis :**
- Mobile : < 768 px → `font-size: 14px`, grilles 1 colonne, tables en scroll horizontal, padding compact
- Desktop : ≥ 768 px → `font-size: 16px`, sidebar fixe 220 px, layout multi-colonnes

**Navigation mobile :**
- Topbar hamburger fixe (hauteur 3.25 rem)
- Menu overlay plein écran
- Sélecteur de langue **absent** du menu mobile (interface exclusivement en français — la fonctionnalité i18n est réservée à une version ultérieure)
- Pas de sidebar latérale sur mobile

**Bouton d'action page (`.page-header-btn`) sur mobile :**

- Le `.page-header` passe en `flex-direction: column` avec `align-items: flex-start` → le bouton est aligné à gauche à sa largeur naturelle (pas pleine largeur, pas centré).
- Le `.page-header` est `position: sticky; top: 3.25rem` sur mobile pour rester visible lors du défilement vers les onglets.
- Ne jamais forcer `width: 100%` sur `.page-header-btn` — cela dénature le bouton sur mobile.
- Référence visuelle : page Actualités (bouton compact, aligné gauche sous le titre).

2. Éco‑conception (Green IT)

Minimiser le poids des pages, scripts et images.
Préconiser les formats AVIF/WebP/SVG.
Activer le lazy‑loading pour images/iframes.
Limiter les animations et vidéos non essentielles.
Favoriser le cache navigateur et HTTP/3.

3. Accessibilité (A11y — WCAG 2.2)

Utiliser des balises HTML sémantiques.
Garantir un contraste suffisant (≥ 4.5:1).
Fournir des alternatives textuelles (alt, aria-label).
Rendre les interactions accessibles au clavier.
Utiliser des labels explicites dans les formulaires.
Tout bouton icône-only (sans libellé textuel visible) doit porter `aria-label` (lu par les lecteurs d'écran) **et** `title` (infobulle au survol) \u2014 voir le tableau des icônes standardisées dans la charte graphique.

4. Internationalisation (i18n)

Séparer contenu et traductions.
Gérer les formats locaux (dates, nombres, devises).
Générer un design compatible avec des textes longs.
Prévoir le support RTL (right‑to‑left) si pertinent.

> **État actuel :** l'application est déployée exclusivement en français. Le sélecteur FR/EN a été retiré de l'interface (menu mobile et sidebar). L'infrastructure i18n (store `locale`, labels `NAV_LABELS`) est conservée dans le code pour une activation ultérieure.

5. Performance

Encourager minification, compression Brotli et bundling.
Fragmenter le code (code‑splitting, lazy‑imports).
Utiliser des CDN et stratégies de cache efficaces.
Réduire le nombre d'appels réseau et la taille JSON.

6. UX / UI Modernes

Favoriser un design minimaliste, lisible et cohérent.
Proposer dark mode + light mode.
Utiliser des micro‑interactions légères et non invasives.
S'appuyer sur un design system ou tokens de design.

**Règles d'affichage des publications (Actualités, Tableau de bord) :**
- **Urgence** : l'état urgent est signalé uniquement par le bord gauche rouge épais de la carte. Aucun badge texte « 🚨 » ou « 🚨 Urgent » ne doit être affiché (redondance visuelle).
- **Ordre des éléments dans la ligne** : `[📌 pin coin] [Brouillon?] Titre [Statut] [🔹 Périmètre]`. Les badges Statut et Périmètre se placent **après** le titre, jamais avant.
- **Distinction lieu / périmètre** : `📍` = lieu physique (adresse, salle…), `🔹` = périmètre logique (Parking, Bât. 1, Cave…). Ne jamais utiliser le même emoji pour les deux.
- **Encodage emojis** : les emojis non-BMP (U+10000+) doivent être encodés en `\u{HEX}` (JS) ou `&#xHEX;` (HTML), jamais en littéral. Voir `specs/design/charte-graphique.md § Convention d'encodage`.
- **Épingle** : affichée en badge absolu coin haut-gauche de la carte, hors du flux inline.

7. Confidentialité & RGPD

Ne collecter que les données strictement nécessaires (minimisation).
Informer clairement l'utilisateur sur l'usage de ses données.
Permettre l'accès, la modification et la suppression des données personnelles.
Pas de trackers tiers, pas de cookies publicitaires.
8. Sécurité

Utiliser HTTPS obligatoire.
Préconiser une CSP stricte.
Mitiger XSS, CSRF et injections.
Stocker les tokens en cookies sécurisés (HttpOnly / Secure).

9. Divulgation progressive (Progressive Disclosure)

Ne pas afficher simultanément toutes les fonctionnalités : exposer progressivement selon le niveau d'engagement.
À la première connexion, déclencher un onboarding guidé (4 étapes non bloquantes, skippables, relançables).
Les écrans vides (tableau de bord sans contenu) doivent proposer une action immédiate (CTA contextuel) plutôt qu'un écran blanc ou un message d'erreur.
Afficher une barre de complétion de profil jusqu'à ce que l'utilisateur l'ait complété à 100 %.
Proposer un résumé de notifications (digest hebdomadaire/quotidien) pour éviter la surcharge : opt-in, configurable.

10. Droits restreints expliqués (Explainable Restrictions)

Ne jamais masquer silencieusement un bouton ou une action si l'utilisateur est susceptible de chercher cette fonctionnalité.
Lorsqu'une action est hors du périmètre d'un rôle (mandataire, syndic, locataire), afficher un message explicatif : « Cette action est réservée à [rôle] » + canal de contact alternatif si pertinent.
Les fonctionnalités futures ou conditionnelles (ex. vote électronique nécessitant un quorum) doivent apparaître avec un état désactivé documenté, et non être invisibles.
L'interface mandataire doit être explicitement réduite au lot mandaté : pas d'autres sections de la résidence visibles.
