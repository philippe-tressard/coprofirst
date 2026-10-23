/*
 *  **La taille du texte suit la préférence, et un champ ne fait pas zoomer
 *  iOS** (#2165, #2166 — arbitrage n° 76, sur maquette le 23/10/2026).
 *
 *  La racine valait 12 px sur téléphone : le texte de lecture tombait à
 *  10,8 px et chaque appui dans un champ (texte < 16 px) faisait agrandir la
 *  page par iOS. Au bureau, `16px` écrasait la taille choisie dans le
 *  navigateur. Ce test mesure ce que le navigateur RENDE, sur les deux profils.
 */
import { attendreHydratation, expect, test } from './aides';

test('la racine vaut 16 px au bureau, 14 px au téléphone ; un champ y fait 16 px', async ({
	page,
}) => {
	const telephone = test.info().project.name === 'mobile';
	await page.goto('/auth/connexion');
	await attendreHydratation(page);
	const taille = (sel: string) =>
		page
			.locator(sel)
			.first()
			.evaluate((e) => parseFloat(getComputedStyle(e).fontSize));

	expect(await taille('html')).toBe(telephone ? 14 : 16);
	if (telephone) {
		expect(await taille('input[type=email]')).toBeGreaterThanOrEqual(16);
		expect(await taille('input[type=password]')).toBeGreaterThanOrEqual(16);
	}
});

test('la racine suit la taille de texte choisie dans le navigateur', async ({ page }) => {
	const telephone = test.info().project.name === 'mobile';
	//  La préférence « taille de police » du navigateur, posée à 20 px.
	const cdp = await page.context().newCDPSession(page);
	await cdp.send('Page.setFontSizes', { fontSizes: { standard: 20 } });
	await page.goto('/auth/connexion');
	await attendreHydratation(page);
	const racine = await page
		.locator('html')
		.evaluate((e) => parseFloat(getComputedStyle(e).fontSize));
	expect(racine).toBe(telephone ? 17.5 : 20);
});
