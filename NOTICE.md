# NOTICE — CoproFirst

**Projet** : CoproFirst, né pour la résidence 5Hostachy (dépôt `coprofirst`, nommé `5hostachy` jusqu'au 09/10/2026)
**Copyright** © 2024-2026 Philippe TRESSARD
**Licence** : GNU Affero General Public License, version 3 ou (à votre choix)
toute version ultérieure — `AGPL-3.0-or-later` (texte officiel : [`LICENSE`](LICENSE))
**Site** : <https://5hostachy.fr>

---

## 1. De quoi il s'agit

CoproFirst est un logiciel de gestion, de documentation et d'organisation pour
les copropriétés et ensembles immobiliers. C'est un **logiciel libre** : chacun
peut l'utiliser, l'étudier, le modifier et le redistribuer, y compris à titre
commercial, dans les conditions de l'AGPL-3.0-or-later.

Ce fichier porte les mentions de copyright du projet et rappelle, sans les
remplacer, les obligations de la licence. **Seul le texte de [`LICENSE`](LICENSE)
fait foi.** Il est en anglais : la Free Software Foundation ne reconnaît aucune
traduction officielle.

## 2. Changement de licence (08/10/2026)

Jusqu'à la version **2.115.0** comprise, le projet était distribué sous la
« Licence 5Hostachy », source-available avec une clause d'usage commercial. Ces
versions déjà publiées **restent** sous leur licence d'origine, lisible dans
leur propre fichier `LICENSE`. À partir de la version **2.116.0**, le projet est
sous AGPL-3.0-or-later, sans condition additionnelle (§7 de la licence).

Le changement a été possible parce que le projet n'a qu'un seul auteur : aucun
contributeur extérieur n'a versé de code sous l'ancienne licence.

## 3. Ce que la licence demande, en bref

- **Conserver** les mentions de copyright et de licence, et ce fichier.
- **Redistribuer** une version modifiée sous la même licence, en indiquant
  qu'elle a été modifiée et quand (AGPL §5).
- **Mise à disposition par le réseau** (AGPL §13) : qui fait fonctionner une
  version modifiée comme service en ligne doit proposer à ses utilisateurs le
  **code source correspondant** de la version qu'ils utilisent. Le site d'origine
  le fait par le lien « CoproFirst » de son pied de page.
- **Aucune garantie** : le logiciel est fourni « tel quel » (AGPL §15 et §16).

## 4. Noms et logo

La licence porte sur le **code**. Elle ne cède aucun droit sur les noms
**5Hostachy** et **CoproFirst** — ce dernier fait l'objet d'une demande de
marque (INPI n° 5307183, 09/10/2026). Les fichiers du **logo** ne sont pas sous
l'AGPL : ils ont leur propre licence d'usage,
[`LICENSES/LicenseRef-CoproFirst-Logo.txt`](LICENSES/LicenseRef-CoproFirst-Logo.txt),
déclarée dans `REUSE.toml`. Ce qui est permis et ce qui ne l'est pas, pour les
noms comme pour le logo : [`MARQUE.md`](MARQUE.md).

## 5. Contributions

Toute contribution est versée sous la même licence, AGPL-3.0-or-later. En
proposant une modification, son auteur accepte qu'elle soit intégrée au projet
sous ces conditions.

## 6. Composants tiers

CoproFirst s'appuie sur des bibliothèques et des contenus tiers. **Ils restent
sous leur propre licence** : la licence du projet ne s'applique pas à eux, et
leurs mentions se conservent avec eux.

L'inventaire complet — chaque dépendance de `front/`, `whatsapp-bridge/` et
`api/` avec sa licence — est [`docs/licences-tierces.md`](docs/licences-tierces.md).
Il est **généré** et vérifié par l'intégration continue, qui échoue sur toute
licence ni admise ni déclarée ; la politique et les motifs des exceptions vivent
dans `scripts/ci/licences_politique.py`.

### Contenus repris dans le dépôt

- **Icônes Lucide** (<https://lucide.dev>) — tracés recopiés dans
  `front/src/lib/icones-svg.json`, sa copie `api/app/utils/icones-svg.json`, les
  deux exemplaires du manuel utilisateur et `infra/cloudflare-worker.js`.
  Licence ISC, `Copyright (c) 2026 Lucide Icons and Contributors` ; pour les
  icônes dérivées de Feather, licence MIT, `Copyright (c) 2013-present Cole Bemis`.
  Textes et mentions :
  [`LICENSES/ISC.txt`](LICENSES/ISC.txt) et [`LICENSES/MIT.txt`](LICENSES/MIT.txt).
- **Logo WhatsApp** (tracé de Simple Icons, <https://simpleicons.org>) — versé
  au domaine public sous CC0-1.0 ([`LICENSES/CC0-1.0.txt`](LICENSES/CC0-1.0.txt)).
  CC0 ne cède aucun droit de marque : le logo reste une marque de son titulaire.

- **Badge « Télécharger dans l'App Store »** — œuvre et marque d'Apple Inc., reprise sans
  modification dans `front/static/badge-app-store-fr.svg` pour le manuel utilisateur. Hors de
  l'AGPL : [`LICENSES/LicenseRef-Apple-App-Store-Badge.txt`](LICENSES/LicenseRef-Apple-App-Store-Badge.txt).

L'attribution de ces fichiers est déclarée dans `REUSE.toml`, et contrôlée par
`scripts/ci/contenus_tiers.py`.

### Composants sous licence non permissive

- **`libsignal` (GPL-3.0)**, tiré par `baileys`, est utilisé dans le **service
  de messagerie `whatsapp-bridge/`**. Ce service s'exécute dans un **conteneur
  distinct** de l'API et de l'interface, avec lesquels il communique
  **uniquement par HTTP**. Les binaires de `libvips` (LGPL-3.0-or-later),
  embarqués par `sharp`, vivent dans le même conteneur.
- Côté API : `certifi` (MPL-2.0) et `pyphen` (GPL 2.0+ / LGPL 2.1+ / MPL 1.1,
  selon son propre fichier de licence), tous deux utilisés sans modification.

Leur compatibilité avec l'AGPL-3.0-or-later a été analysée le 08/10/2026 et
**validée par l'auteur** ; le motif de chacune est écrit dans
`scripts/ci/licences_politique.py`. Ce fichier constate où ces composants sont
employés et comment ; il ne constitue pas un avis juridique.
