/*
 *  **Les entrées « Guide » des deux menus se tiennent comme une entrée de menu.**
 *
 *  `LiensGuide` recevait la classe de son menu en prop (`class="{classe} …"`) et
 *  comptait sur deux règles `:global` de `Nav.svelte` pour la rendre : un fichier
 *  aveugle à `lint:css-orphelin` (#1571). Il porte désormais son habillage. Un
 *  style qui manquerait ne lèverait rien : le lien resterait en ligne, sans
 *  gouttière ni coins. Les valeurs ci-dessous sont celles MESURÉES avant le
 *  déplacement (21/10/2026), bureau et mobile, ramenées en rem.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

//  En REM, jamais en pixels : la taille de base de la page peut changer en cours de
//  test (réglage d'affichage chargé après l'hydratation) — les mêmes valeurs se
//  lisaient 13,6 px un jour et 10,2 px le suivant, à un facteur 0,75 près.
const ENTREE = {
	display: 'flex',
	alignItems: 'center',
	columnGap: 0.6,
	padding: [0.55, 0.7, 0.55, 0.7],
	borderRadius: 0.5,
	color: 'rgb(26, 26, 46)',
	fontSize: 0.85,
	textDecorationLine: 'none',
};

async function rendu(page: import('@playwright/test').Page, selecteur: string) {
	return page.locator(selecteur).evaluateAll((els) =>
		els.map((el) => {
			const c = getComputedStyle(el);
			const base = parseFloat(getComputedStyle(document.documentElement).fontSize);
			const rem = (v: string) => Math.round((parseFloat(v) / base) * 1000) / 1000;
			return {
				display: c.display,
				alignItems: c.alignItems,
				columnGap: rem(c.columnGap),
				padding: [c.paddingTop, c.paddingRight, c.paddingBottom, c.paddingLeft].map(rem),
				borderRadius: rem(c.borderRadius),
				color: c.color,
				fontSize: rem(c.fontSize),
				textDecorationLine: c.textDecorationLine,
			};
		}),
	);
}

test('le guide du menu latéral est habillé comme une entrée de menu', async ({
	page,
	isMobile,
}) => {
	test.skip(!!isMobile, 'le menu latéral est masqué sur mobile');
	await simulerApi(page);
	await page.goto('/sondages');
	await attendreHydratation(page);

	const liens = page.locator('a.nav-guide');
	await expect(liens).toHaveCount(1);
	await expect(liens).toHaveText(/Guide/);
	expect(await rendu(page, 'a.nav-guide')).toEqual([ENTREE]);
});

test('le guide du menu mobile, en ligne et en PDF, est habillé de même', async ({
	page,
	isMobile,
}) => {
	test.skip(!isMobile, 'le menu mobile ne s’ouvre que sur mobile');
	await simulerApi(page);
	await page.goto('/sondages');
	await attendreHydratation(page);
	await page.getByRole('button', { name: 'Menu' }).click();

	const liens = page.locator('.overlay-footer a.nav-guide');
	await expect(liens).toHaveCount(2);
	expect(await rendu(page, '.overlay-footer a.nav-guide')).toEqual([ENTREE, ENTREE]);
});
