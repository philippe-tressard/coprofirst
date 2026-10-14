/*
 *  **Un composant chargé au geste n'annonce son attente qu'au-delà de 300 ms.**
 *
 *  Le morceau est le plus souvent déjà en cache : « Chargement… » clignotait
 *  une fraction de seconde à chaque onglet (`ChargementDiffere`, 12/10/2026).
 *  Ce qu'on tient, le module de l'onglet Contrats RETENU : l'attente est
 *  invisible d'abord, apparaît ensuite en fondu, puis l'onglet se rend.
 */
import { attendreHydratation, expect, retenirModule, simulerApi, test } from './aides';

test('l’attente d’un onglet chargé au geste ne clignote pas', async ({ page }) => {
	await simulerApi(page);
	const relacher = await retenirModule(page, 'OngletContrats.svelte');
	await page.goto('/prestataires');
	await attendreHydratation(page);
	await page
		.getByRole('tablist')
		.getByRole('link', { name: /Contrats/ })
		.click();

	const attente = page.locator('.attente-differee');
	await expect(attente).toBeAttached();
	//  Le délai se lit dans le style calculé, pas en mesurant l'opacité à un
	//  instant donné : sous charge, l'instant dépasserait les 300 ms (#1830).
	await expect(attente).toHaveCSS('animation-delay', '0.3s');
	await expect(attente).toHaveCSS('animation-fill-mode', 'both');
	const opacite = () => attente.evaluate((n) => Number(getComputedStyle(n).opacity));
	await expect.poll(opacite).toBeGreaterThan(0.9);
	relacher();
	await expect(attente).toHaveCount(0);
});
