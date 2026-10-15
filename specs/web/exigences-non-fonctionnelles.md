# Exigences non fonctionnelles — Site web

---

## Performance

- First Contentful Paint (FCP) < 2 s sur connexion 4G / fibre standard.
- Time to Interactive (TTI) < 3 s.
- Taille du bundle JS < 150 Ko gzippé (SvelteKit).
- Les images utilisent les formats AVIF/WebP avec fallback PNG/JPEG.
- Lazy-loading activé sur toutes les images et iframes hors-écran.
- Cache HTTP actif pour les assets statiques (headers `Cache-Control: immutable`).

---

## Accessibilité

- Niveau visé : **WCAG 2.2 AA** (cible AAA pour les pages critiques).
- Contraste texte/fond ≥ 4,5:1 (corps de texte), ≥ 3:1 (grand texte et UI).
- Navigation 100 % au clavier (focus visible, ordre de tabulation logique).
- Attributs ARIA pour les composants interactifs (modales, menus, alertes).
- Alternatives textuelles sur toutes les images (`alt`, `aria-label`).
- Labels explicites sur tous les champs de formulaire.
- Respect de `prefers-reduced-motion` (désactivation des animations).
- Respect de `prefers-color-scheme` (dark mode / light mode).

---

## Compatibilité navigateurs

| Navigateur | Version minimale |
|------------|------------------|
| Chrome | 120+ |
| Firefox | 120+ |
| Safari | 16.4+ |
| Edge | 120+ |
| Safari iOS | 16.4+ |
| Chrome Android | 120+ |

- Pas de support d'Internet Explorer.
- Prise en charge du mode responsive dès 320 px de largeur.

---

## SEO

- Rendu SSR (SvelteKit) : chaque page expose un HTML complet aux crawlers.
- Balises `<title>` et `<meta name="description">` uniques par page.
- Balises Open Graph pour les pages partageables.
- Fichier `robots.txt` et `sitemap.xml` générés automatiquement.
- URLs sémantiques et lisibles (pas de hash, pas de paramètres opaques).

---

## Sécurité

- HTTPS obligatoire (Caddy + Let's Encrypt, TLS 1.2 minimum, TLS 1.3 recommandé).
- CSP (Content Security Policy) stricte — pas d'`unsafe-inline` en production.
- Protection CSRF via cookies `SameSite=Strict` + token double-submit si nécessaire.
- Tokens JWT stockés en cookies `HttpOnly` + `Secure` (jamais dans `localStorage`).
- En-têtes de sécurité : `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`.
- Validation des entrées côté serveur (Pydantic v2) — ne jamais faire confiance au client.
- Aucune donnée sensible dans les logs ni dans les URLs.
- Dépendances vérifiées régulièrement (Dependabot ou équivalent).

### Autorisation — centralisation sans exception

Exigence de même rang que la factorisation du code, et pour la même raison : une
règle dupliquée cesse d'être une règle.

- **Toute** dépendance d'autorisation est définie dans `api/app/auth/deps.py`. Aucune
  règle locale à un routeur : elle échapperait à tout durcissement du module central.
- Tout endpoint porte une dépendance d'autorisation. Les exceptions publiques sont
  **énumérées et justifiées** une à une (cf. `specs/architecture/api.md`), jamais
  implicites.
- Les contrôles de rôle passent par `has_role(RoleUtilisateur.…)` — jamais par
  `user.role` (rôle principal seul), jamais par chaîne littérale.
- **Tout filtre exposant des données sans authentification est une liste blanche.**
  Une liste noire échoue en s'ouvrant : ce qui n'est pas interdit devient public par
  défaut, donc chaque donnée nouvelle fuit en silence. Une liste blanche échoue en se
  fermant — la donnée manquante casse un écran, ce qui se voit et se corrige.

Ces quatre points sont vérifiés automatiquement par `api/tests/test_autorisation.py`,
exécuté en CI. Ils ne relèvent pas de la relecture : l'audit du 26/07/2026 a montré
que trois dérives s'étaient installées sans que personne ne les remarque, dont une
que la spec elle-même avait légitimée.

---

## Éco-conception

- Pas de framework CSS lourd (pas de Bootstrap / Tailwind CDN).
- Polices chargées en local ou via `font-display: swap`.
- Animations limitées au strict nécessaire, désactivables.
- Aucun tracker tiers, aucun cookie publicitaire (conformité RGPD native).

---

## Conformité RGPD (Règlement UE 2016/679 + Loi Informatique et Libertés)

- Le **syndicat des copropriétaires** est responsable de traitement (Art. 4 RGPD), représenté par le président du conseil syndical.
- Base légale principale : **exécution du contrat** de copropriété (Art. 6.1.b) pour la gestion du lot et des tickets ; **consentement** (Art. 6.1.a) pour les communications optionnelles.
- **Minimisation des données** (Art. 5.1.c) : seuls nom, prénom, email, téléphone, bâtiment, statut et lot(s) sont collectés à l'inscription.
- Durées de conservation définies : compte actif (durée de résidence + 3 ans) ; documents de copropriété (10 ans) ; logs techniques (90 jours).
- Aucun transfert de données hors UE sans clauses contractuelles types de la Commission européenne — inclut les fournisseurs OAuth (Apple, Google).
- Les mineurs de moins de **15 ans** ne peuvent pas s'inscrire (Art. 8 RGPD + Loi n° 2018-493 du 20 juin 2018).
- Un **registre des activités de traitement** (Art. 30) est maintenu par l'admin et exportable.
- Les violations de données sont notifiées à la **CNIL** sous **72 heures** (Art. 33) et aux personnes concernées si risque élevé (Art. 34).
- Les exigences fonctionnelles associées sont EF-WEB-001, EF-WEB-090, EF-WEB-091, EF-WEB-092.

---

## Conformité LCEN (Loi n° 2004-575 du 21 juin 2004)

- Une page **Mentions légales** est publiée et accessible sans authentification (Art. 6 LCEN), listant l'éditeur (syndicat des copropriétaires), le directeur de publication (président du conseil syndical) et l'hébergeur.
- Tous les emails émis par l'application respectent l'obligation anti-spam (LCEN + CPCE Art. L33-4-1) : identité de l'expéditeur, lien de désinscription pour les communications non essentielles, consentement opt-in préalable.
- Les en-têtes d'authentification email **SPF**, **DKIM** et **DMARC** sont configurés sur le domaine d'envoi.
- Voir EF-WEB-100 (Mentions légales) et EF-WEB-101 (anti-spam).

---

## Conformité Loi ALUR (2014) / ELAN (2018) — Extranet copropriété

- **5Hostachy constitue l'extranet légal** de la résidence au sens de l'Art. 18-2 de la Loi du 10 juillet 1965 modifiée par ALUR et ELAN : espace en ligne sécurisé donnant accès aux documents et informations de la copropriété.
- L'application doit permettre l'accès aux documents suivants depuis tout compte résident actif : PV d'assemblée générale, règlement de copropriété, carnets d'entretien, diagnostics techniques, plans de la résidence.
- Les PV d'AG doivent être conservés et accessibles un minimum de **10 ans** (Loi 1965 Art. 33 + Décret 1967).
- La fiche synthétique annuelle de la copropriété (Art. 8-2 Loi 1965) doit être publiée par l'admin/conseil syndical chaque année et accessible à tous les résidents.

---

## Cybersécurité — Directive NIS2 (UE 2022/2555) et recommandations ANSSI

> La directive NIS2 ne s'applique pas directement à une copropriété privée, mais l'auto-hébergement sur un réseau local exposé impose les bonnes pratiques correspondantes.

- **Mises à jour de sécurité** : le Raspberry Pi, Docker Engine et les images de conteneurs doivent être mis à jour au minimum mensuellement (Watchtower optionnel, cron manuel sinon).
- **Cloisonnement réseau** : le RPi n'expose que les ports 80 et 443 (HTTP/HTTPS). L'accès SSH (port 22) est restreint au réseau local `192.168.1.0/24` via UFW — toute connexion SSH depuis l'extérieur est bloquée. L'interface d'administration Docker et la base PostgreSQL ne sont jamais exposées (la réplication n'écoute que sur le LAN, depuis l'autre nœud).
- **Sauvegardes testées** : la procédure de restauration depuis backup doit être testée au minimum une fois par trimestre.
- **Gestion des incidents** : en cas de compromission constatée (accès non autorisé, fuite de données), le conseil syndical dispose d'une procédure écrite de notification aux résidents et à la CNIL (Art. 33-34 RGPD).
- **Authentification** : MFA recommandé pour les comptes `admin` et `conseil_syndical` (ANSSI, CERTFR-2021-AVI).
- **Journalisation** : logs d'accès Caddy conservés 90 jours, logs applicatifs (FastAPI) incluant les authentifications réussies/échouées, sans données personnelles dans les messages de log.

---

## eIDAS — Valeur probatoire des actions numériques

> Applicable uniquement si l'application étend son périmètre aux votes d'assemblée générale dématérialisés (hors périmètre MVP).

- Les **sondages internes** (EF-WEB-031) sont des outils de consultation informelle ; ils n'ont pas valeur de décision d'AG et ne sont pas soumis à eIDAS.
- Si, en phase ultérieure, des résolutions d'AG sont signées ou votées en ligne, une **signature électronique avancée** (niveau eIDAS 2, Règlement UE 910/2014) est requise pour la valeur probatoire.

---

## Conformité juridique — Licences open source

- Toute dépendance tierce (npm, PyPI) doit être licenciée sous une licence compatible avec un usage commercial : MIT, Apache 2.0, BSD, ISC. Les licences copyleft fortes (GPL, AGPL) sont interdites sans validation explicite.
- Un inventaire des licences est généré automatiquement à chaque build de production (outil : `license-checker` côté front, `pip-licenses` côté API).
- L'application expose une page **À propos / Licences** accessible depuis les paramètres, listant les bibliothèques utilisées avec leur nom, version, auteur et texte de licence complet.
- Les mentions de copyright imposées par les licences (ex. Apache 2.0 `NOTICE`, MIT copyright header) sont incluses dans cette page et dans le fichier `LICENSES.md` du dépôt.
- Aucune bibliothèque sans licence identifiée ne peut être intégrée en production.
