/**
 *  La PALETTE de la copropriété (#2379, 30/10/2026) — les couleurs du site, que
 *  l'administration choisit à côté du logo (`ChampPalette`).
 *
 *  ## Qui décide de quoi
 *
 *  - le REGISTRE (codes, noms, couleurs des courriels et des affiches) est dans
 *    l'API, `utils/palettes.py` : l'écran le lit par `GET /config/palettes` ;
 *  - les JETONS du site, clair et sombre, sont dans `styles/palettes.css`, sous
 *    `:root[data-palette='…']` ;
 *  - ce module ne connaît que la FORME d'un code et pose l'attribut. Un code
 *    sans règle dans la feuille laisse la charte, rien ne casse.
 *
 *  Le serveur pose l'attribut à la page (`hooks.server.ts`, repère `%palette%`
 *  de `app.html`) : elle se peint d'emblée aux couleurs de la copropriété, écran
 *  de connexion compris. 🔒 `api/tests/test_palettes.py` confronte les codes et
 *  les valeurs de la feuille au registre.
 */

/** La clé de configuration (`GET /config`, publique). */
export const CLE_PALETTE = 'site_palette';
/** La charte : aucune règle dans `palettes.css`, les valeurs de `socle.css`. */
export const PALETTE_PAR_DEFAUT = 'seine';

const FORME = /^[a-z]{1,24}$/;
const REPERE = '%palette%';

/** Le code d'une valeur de configuration : absent ou mal formé → la charte. PURE. */
export function lirePalette(valeur: string | null | undefined): string {
	const v = (valeur ?? '').trim();
	return FORME.test(v) ? v : PALETTE_PAR_DEFAUT;
}

/** Le gabarit de page avec sa palette — appelé par `hooks.server.ts`. PURE. */
export function remplirPalette(html: string, valeur: string | null | undefined): string {
	return html.replace(REPERE, lirePalette(valeur));
}

/** Applique une palette à la page ouverte — ce que le serveur aurait écrit. */
export function appliquerPalette(valeur: string | null | undefined): void {
	document.documentElement.dataset.palette = lirePalette(valeur);
}
