/*
 *  **Le liseré de l'onglet actif se voit EN ENTIER (28/10/2026).**
 *
 *  Signalé à l'écran : « on ne voit pas le sous-menu sélectionné ». La rangée
 *  `.tabs` de `BarreOnglets` défile en largeur, donc masque son axe vertical
 *  (`overflow-y: hidden`) — et ce masquage rogne au bord du rembourrage. Le
 *  liseré, qui chevauchait la bordure par une marge négative, y perdait sa
 *  moitié basse. Ce test mesure que l'onglet actif tient dans la zone visible
 *  de la rangée, sur les profils bureau et mobile.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

test('l’onglet actif n’est pas rogné par sa rangée', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/llm-usages') return [];
		return undefined;
	});
	await page.goto('/admin?onglet=utilisateurs');
	const actif = page.locator('.tabs .tab-btn.active');
	await expect(actif).toHaveText(/Utilisateurs/);
	//  Le liseré est le BAS de la rangée : ni rembourrage, ni bordure, ni rognage
	//  sous lui. Avant le correctif, 1,6 px de rembourrage le décollait de la ligne
	//  et le masquage en rognait 0,4 px.
	const ecart = await actif.evaluate(
		(el) =>
			(el.parentElement as HTMLElement).getBoundingClientRect().bottom -
			el.getBoundingClientRect().bottom,
	);
	expect(Math.abs(ecart)).toBeLessThanOrEqual(0.25);
	await expect(actif).toHaveCSS('border-bottom-width', '2px');
});
