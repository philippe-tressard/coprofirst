/*
 *  **Les entrées « Guide » des deux menus se tiennent comme une entrée de menu.**
 *
 *  `LiensGuide` recevait la classe de son menu en prop (`class="{classe} …"`) et
 *  comptait sur deux règles `:global` de `Nav.svelte` pour la rendre : un fichier
 *  aveugle à `lint:css-orphelin` (#1571). Il porte désormais son habillage. Un
 *  style qui manquerait ne lèverait rien : le lien resterait en ligne, sans
 *  gouttière ni coins. Les valeurs ci-dessous sont celles MESURÉES avant le
 *  déplacement (21/10/2026), bureau et mobile.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

const ENTREE = {
	display: 'flex',
	alignItems: 'center',
	columnGap: '9.6px',
	padding: '8.8px 11.2px',
	borderRadius: '8px',
	color: 'rgb(26, 26, 46)',
	fontSize: '13.6px',
	textDecorationLine: 'none',
};

async function rendu(page: import('@playwright/test').Page, selecteur: string) {
	return page.locator(selecteur).evaluateAll((els) =>
		els.map((el) => {
			const c = getComputedStyle(el);
			return {
				display: c.display,
				alignItems: c.alignItems,
				columnGap: c.columnGap,
				padding: c.padding,
				borderRadius: c.borderRadius,
				color: c.color,
				fontSize: c.fontSize,
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
