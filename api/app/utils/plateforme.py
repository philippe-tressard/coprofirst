"""La PLATEFORME — le logiciel qui sert la résidence, et non la résidence (#1725).

Deux noms, deux réglages, et les confondre est le défaut que ce module ferme :

| | Ce qu'il nomme | Où il se lit |
|---|---|---|
| **la résidence** | celle qu'on habite, « 5Hostachy » ici | `site_nom`, en base — `liens.nom_site` |
| **la plateforme** | le logiciel, le même pour toutes | ICI, et nulle part ailleurs |

Arbitrage du 07/10/2026, revu le 09/10/2026 (`specs/architecture/multi-coproprietes.md`,
D9) : la plateforme s'appelle **CoproFirst** (« CoproConnect » du 07 au 09/10/2026, abandonné : une startup du même domaine porte déjà ce nom (#1772)). Le nom de la résidence, lui, était écrit
« 5Hostachy » dans le titre de l'API, le `User-Agent` des appels sortants, les
mentions légales et le manuel PDF : le nom d'une copropriété employé pour
désigner le logiciel de toutes.

🔴 Le front porte la **même** déclaration (`front/src/lib/plateforme.ts`) : les
contextes de build `./api` et `./front` ne partagent aucun fichier.
`tests/test_plateforme.py` échoue si les deux divergent.

La licence est l'**AGPL-3.0-or-later** depuis le 08/10/2026 (#1726) : ses trois
constantes sont tenues contre `REUSE.toml` et `LICENSE` par `test_plateforme.py`.
"""

#: Le nom du logiciel — l'attribution, le titre de l'API, le `User-Agent`.
#:
#: Le lien vers le source de la VERSION qui tourne (AGPLv3 §13) se compose côté
#: front, seul à connaître l'empreinte du build (`lienSource`, `VITE_GIT_HASH`).
NOM_PLATEFORME = "CoproFirst"

#: Le dépôt public du code source, au nom du logiciel depuis le 09/10/2026
#: (#1772) : il portait celui de la résidence, et l'ancienne adresse redirige.
#: `scripts/ci/descriptif_depot.py` vérifie que GitHub le sert à cette adresse.
DEPOT_SOURCE = "https://github.com/philippe-tressard/coprofirst"

#: Le site de présentation du logiciel : le NOM de la plateforme y renvoie dans les
#: mentions légales. Le front le lie aussi (pied de page, `plateforme.ts`).
SITE_PLATEFORME = "https://coprofirst.fr"

#: La licence, telle qu'on l'identifie, la nomme et la lie. Le texte qui fait
#: foi est l'officiel, en anglais (`LICENSE`).
LICENCE_SPDX = "AGPL-3.0-or-later"
LICENCE_NOM = "GNU Affero General Public License, version 3 ou ultérieure"
LICENCE_URL = f"{DEPOT_SOURCE}/blob/main/LICENSE"
