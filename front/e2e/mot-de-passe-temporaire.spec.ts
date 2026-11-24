/*
 *  **Un mot de passe temporaire se change avant d'entrer** (#3019).
 *
 *  Les deux comptes initiaux d'une installation neuve naissent avec un mot de
 *  passe écrit au journal du conteneur ; l'API leur refuse tout, sauf leur profil
 *  et le changement (`api/tests/test_mot_de_passe_a_changer.py` le prouve côté
 *  serveur). Ici, l'écran : un compte marqué qui ouvre une page de l'application
 *  arrive sur le changement, la page demandée en mémoire ; le changement fait, il
 *  y va. Le compte est simulé (`MEMBRE_CS`, marqué) : ce que l'API refuse n'est
 *  pas éprouvé ici.
 */
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

test('un compte au mot de passe temporaire est mené au changement, puis où il allait', async ({
	page,
}) => {
	let marque = true;
	let change: unknown = null;
	await simulerApi(page, (chemin) =>
		chemin === '/api/auth/me' ? { ...MEMBRE_CS, mot_de_passe_a_changer: marque } : undefined,
	);
	await page.route(
		(url) => url.pathname === '/api/auth/change-password',
		async (route) => {
			change = route.request().postDataJSON();
			marque = false;
			await route.fulfill({ status: 204 });
		},
	);

	//  Ce que la page du changement appelle, une fois qu'on y est.
	const appels: string[] = [];
	page.on('request', (r) => {
		const url = new URL(r.url());
		if (url.pathname.startsWith('/api/') && page.url().includes('/auth/mot-de-passe-temporaire'))
			appels.push(`${r.method()} ${url.pathname}`);
	});
	await page.goto('/notifications');
	await expect(page).toHaveURL(/\/auth\/mot-de-passe-temporaire\?next=%2Fnotifications$/);
	await attendreHydratation(page);
	//  L'écran du changement, sans le menu de l'application.
	await expect(page.locator('.auth-header p')).toHaveText('Choisir votre mot de passe');
	await expect(page.locator('nav')).toHaveCount(0);

	await page.locator('#pwd-actuel').fill('Temporaire-Journal-1');
	await page.locator('#pwd-nouv').fill('Nouveau-Secret-2026');
	await page.locator('#pwd-conf').fill('Nouveau-Secret-2026');
	await page.getByRole('button', { name: 'Modifier le mot de passe' }).click();

	await expect(page).toHaveURL(/\/notifications$/);
	expect(change).toEqual({
		mot_de_passe_actuel: 'Temporaire-Journal-1',
		nouveau_mot_de_passe: 'Nouveau-Secret-2026',
	});
	//  La page n'appelle que ce que l'API ouvre à un compte marqué : ses deux routes
	//  admises, et la configuration publique (relevé du 24/11/2026, confronté au balayage
	//  de `test_mot_de_passe_a_changer.py`).
	expect([...new Set(appels)].sort()).toEqual([
		'GET /api/auth/me',
		'GET /api/config',
		'POST /api/auth/change-password',
	]);
});

test('un compte sans mot de passe temporaire ne passe pas par le changement', async ({ page }) => {
	await simulerApi(page);
	await page.goto('/auth/mot-de-passe-temporaire');
	await expect(page).toHaveURL(/\/tableau-de-bord$/);
	//  Le témoin du sélecteur que le premier test attend absent : le menu est là.
	await expect(page.locator('nav').first()).toBeAttached();
});
