/*
 *  **Les entrées « Guide » des deux menus portent la classe de LEUR menu.**
 *
 *  `LiensGuide` recevait sa classe en prop (`class="{classe} nav-guide"`), ce qui
 *  le rendait aveugle à `lint:css-orphelin` (#1571) ; il reçoit désormais un
 *  booléen et pose `nav-item` ou `overlay-item` par `class:`. Une classe qui
 *  manquerait ne lèverait rien : le lien perdrait seulement l'habillage de son
 *  menu. D'où ce test, qui lit les classes posées ET le rendu.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

test('le guide du menu latéral porte nav-item et en prend le rendu', async ({ page, isMobile }) => {
	test.skip(!!isMobile, 'le menu latéral est masqué sur mobile');
	await simulerApi(page);
	await page.goto('/sondages');
	await attendreHydratation(page);

	const guide = page.locator('.enveloppe-guide a.nav-guide');
	await expect(guide).toHaveCount(1);
	await expect(guide).toHaveText(/Guide/);
	await expect(guide).toHaveClass(/\bnav-item\b/);
	await expect(guide).not.toHaveClass(/overlay-item/);
	//  Habillé : sans sa classe de menu, le lien resterait en ligne, sans coins ni gouttière.
	const rendu = await guide.evaluate((el) => {
		const c = getComputedStyle(el);
		return { display: c.display, rayon: c.borderRadius, ecart: c.columnGap };
	});
	expect(rendu.display).toBe('flex');
	expect(rendu.rayon).not.toBe('0px');
	expect(rendu.ecart).not.toBe('normal');
});

test('le guide du menu mobile porte overlay-item, en ligne et en PDF', async ({
	page,
	isMobile,
}) => {
	test.skip(!isMobile, 'le menu mobile ne s’ouvre que sur mobile');
	await simulerApi(page);
	await page.goto('/sondages');
	await attendreHydratation(page);
	await page.getByRole('button', { name: 'Menu' }).click();

	const guides = page.locator('.overlay-footer .enveloppe-guide a.nav-guide');
	await expect(guides).toHaveCount(2);
	for (const g of await guides.all()) {
		await expect(g).toHaveClass(/\boverlay-item\b/);
		await expect(g).not.toHaveClass(/nav-item/);
	}
	await expect(guides.first()).toHaveCSS('display', 'flex');
});
