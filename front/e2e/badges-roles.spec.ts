/*
 *  **Chaque badge de rôle porte une teinte, à l'écran (#1986, 16/10/2026).**
 *
 *  « Propriétaire » s'affichait sans fond ni couleur depuis la v1.0.0 : sa
 *  teinte, `badge-teal`, n'avait de règle dans aucune feuille. `lint:badge`
 *  compare les NOMS (code, composant, feuilles) ; ce test-ci regarde ce qui est
 *  PEINT. Il rend Admin › À traiter, API simulée, avec un compte qui porte tous
 *  les rôles, et exige de chaque badge un fond qui ne soit pas transparent —
 *  la base `.badge` seule n'en pose aucun.
 *
 *  ⚠️ Les rôles se lisent dans `#lib/roles` PAR LE NAVIGATEUR, servis par Vite :
 *  importé ici, le module tirerait `#lib`, que Playwright ne résout qu'après un
 *  `svelte-kit sync` — absent du job e2e, où la collecte de TOUTE la suite
 *  échouerait. Recopier la liste, elle, divergerait au premier rôle ajouté.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

test('Admin › À traiter : chaque badge de rôle a un fond', async ({ page }) => {
	await page.goto('/');
	const LIBELLES_ROLE: Record<string, string> = await page.evaluate(
		async () => (await import('/src/lib/roles.ts')).LIBELLES_ROLE,
	);
	const ROLES = Object.keys(LIBELLES_ROLE);
	expect(ROLES.length, 'rôles lus dans #lib/roles').toBeGreaterThan(1);

	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/comptes-en-attente/enrichis')
			return [{ user: { ...MEMBRE_CS, id: 7, role: ROLES[0], roles: ROLES }, lots_prevus: 0 }];
		return undefined;
	});
	await page.goto('/admin');

	const badges = page.locator('.liste-roles .badge');
	await expect(badges).toHaveCount(ROLES.length);
	for (const role of ROLES) {
		const badge = badges.filter({ hasText: LIBELLES_ROLE[role] });
		await expect(badge, `badge « ${LIBELLES_ROLE[role]} »`).not.toHaveCSS(
			'background-color',
			'rgba(0, 0, 0, 0)',
		);
	}
});
