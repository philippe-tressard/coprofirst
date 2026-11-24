/**
 * Qui voit quelle entrée du menu — LUE, jamais recomposée (#2969, #2905).
 *
 * Le filtre vivait dans `Nav.svelte`, en littéraux de rôles et de statuts, et les
 * apps iOS et Android en portaient chacune une copie : les trois divergeaient, et le
 * syndic n'avait aucune entrée sur le site. Désormais :
 *
 *   · chaque page du menu déclare son PUBLIC (`acces`, `#lib/pages`), publié aux
 *     apps par `tables-clients.json` ;
 *   · le serveur dit à quels publics appartient le compte : `acces_menu` de
 *     `/auth/me`, calculé par `api/app/utils/acces_menu.py` — la règle y est écrite,
 *     avec le pourquoi de chaque public ;
 *   · une page s'affiche si son public est servi. Rien d'autre.
 *
 * Masquer ne protège rien : chaque route tranche ses droits elle-même.
 * 🔒 `api/tests/test_acces_menu.py` (concordance des publics) ; `npm run
 * lint:manuel-menus` (le manuel annonce le public déclaré, et `Nav.svelte` ne
 * nomme aucun rôle).
 */

/** Les publics du menu, ceux que sert `acces_menu`. */
export type AccesMenu = 'tous' | 'resident' | 'cs' | 'cs-ou-aidant' | 'admin';

/** La page s'affiche-t-elle au menu de ce compte ? Défaut fermé : sans public, non. */
export function pageAuMenu(
	page: { acces?: AccesMenu } | undefined,
	accesServis: readonly string[] | null | undefined,
): boolean {
	return !!page?.acces && (accesServis ?? []).includes(page.acces);
}
