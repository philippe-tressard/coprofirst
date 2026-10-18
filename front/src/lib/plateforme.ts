/**
 * La PLATEFORME — le logiciel qui sert la résidence, et non la résidence (#1725).
 *
 * Deux noms, et les confondre est le défaut que ce module ferme :
 *
 * | | Ce qu'il nomme | Où il se lit |
 * |---|---|---|
 * | la résidence | celle qu'on habite | `site_nom`, en base — `siteNomStore` |
 * | la plateforme | le logiciel, le même pour toutes | ICI, et nulle part ailleurs |
 *
 * Arbitrage du 07/10/2026, revu le 09/10/2026 (`specs/architecture/multi-coproprietes.md`,
 * D9) : la plateforme s'appelle CoproFirst (« CoproConnect » du 07 au 09/10/2026, abandonné : une startup du même domaine porte déjà ce nom (#1772)).
 *
 * 🔴 L'API porte la MÊME déclaration (`api/app/utils/plateforme.py`) : les
 * contextes de build `./api` et `./front` ne partagent aucun fichier.
 * `api/tests/test_plateforme.py` échoue si les deux divergent.
 *
 * La licence est l'AGPL-3.0-or-later depuis le 08/10/2026 (#1726).
 */

/** Le nom du logiciel — l'attribution et le lien vers le source. */
export const NOM_PLATEFORME = 'CoproFirst';

/** Le dépôt public du code source, au nom du logiciel depuis le 09/10/2026
 *  (#1772) : il portait celui de la résidence, et l'ancienne adresse redirige. */
export const DEPOT_SOURCE = 'https://github.com/philippe-tressard/coprofirst';

/** Le site de présentation du logiciel — « À propos de CoproFirst », en pied
 *  de page (#2040) ; l'API le lie aussi, sur le nom du logiciel, dans les
 *  mentions légales (`api/app/utils/plateforme.py`). */
export const SITE_PLATEFORME = 'https://coprofirst.fr';

/** La licence, telle qu'on l'identifie, la nomme et la lie. Le texte qui fait
 *  foi est l'officiel, en anglais (`LICENSE`). */
export const LICENCE_SPDX = 'AGPL-3.0-or-later';
export const LICENCE_NOM = 'GNU Affero General Public License, version 3 ou ultérieure';
export const LICENCE_URL = `${DEPOT_SOURCE}/blob/main/LICENSE`;

/**
 * Le code source de la version qui TOURNE — l'AGPLv3 §13 vise celle-là, pas la
 * dernière du dépôt. L'empreinte est celle du build (`VITE_GIT_HASH`) ; sans
 * elle (poste de développement), le dépôt lui-même.
 */
export function lienSource(empreinte?: string | null): string {
	const propre = (empreinte ?? '').trim();
	return !propre || propre === 'dev' ? DEPOT_SOURCE : `${DEPOT_SOURCE}/tree/${propre}`;
}
