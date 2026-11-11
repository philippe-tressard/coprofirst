/*
 *  **La FAQ et les sondages offrent leurs gestes de rédaction selon le droit SERVI** (#2654).
 *
 *  Les deux écrans décidaient par `$isCS` (les rôles du compte) ; l'app iOS relisait
 *  cette règle générée depuis le front. Ils lisent désormais `GET /faq/gestes`
 *  (`peut_rediger`) et `GET /sondages/gestes` (`peut_creer`), que l'API calcule par
 *  le prédicat même de ses routes. La concordance rôle par rôle — et l'égalité avec
 *  ce que `$isCS` ouvrait — est tenue côté serveur
 *  (`api/tests/test_gestes_faq_sondages_servis.py`) ; ici, que l'écran SUIT le champ :
 *  un membre du conseil à qui le serveur ne l'ouvre pas ne voit rien, un résident à
 *  qui il l'ouvre voit les gestes. Les deux écrans ne lisent plus les rôles.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const RESIDENT = { ...MEMBRE_CS, role: 'résident', roles: ['résident'] };

/** Rend `chemin` pour `moi`, le droit servi par `gestes` ; rend les chemins appelés. */
async function ouvrir(
	page: Page,
	chemin: string,
	moi: object,
	gestes: Record<string, unknown>,
): Promise<string[]> {
	const appels: string[] = [];
	await simulerApi(page, (c) => {
		appels.push(c);
		if (c === '/api/auth/me') return moi;
		return gestes[c];
	});
	await page.goto(chemin);
	await attendreHydratation(page);
	return appels;
}

for (const [moi, ouvert] of [
	[MEMBRE_CS, false],
	[RESIDENT, true],
] as const) {
	const qui = `${moi.roles[0]}, droit servi ${ouvert ? 'ouvert' : 'fermé'}`;

	test(`FAQ — ${qui} : « Réorganiser » suit peut_rediger`, async ({ page }) => {
		const appels = await ouvrir(page, '/faq', moi, {
			'/api/faq/gestes': { peut_rediger: ouvert },
		});
		//  Le droit choisit la liste lue — les inactives ne vont qu'au rédacteur — et
		//  elle n'est demandée qu'APRÈS lui : l'écran l'a donc reçu.
		const liste = ouvert ? '/api/faq/all' : '/api/faq';
		await expect.poll(() => appels).toContain(liste);
		await expect(page.getByRole('button', { name: 'Réorganiser' })).toHaveCount(ouvert ? 1 : 0);
	});

	test(`Sondages — ${qui} : « Nouveau sondage » suit peut_creer`, async ({ page }) => {
		const appels = await ouvrir(page, '/sondages', moi, {
			'/api/sondages/gestes': { peut_creer: ouvert },
		});
		await expect.poll(() => appels).toContain('/api/sondages/gestes');
		//  La liste et le droit arrivent ensemble : l'écran a fini de charger.
		await expect(page.getByText('Aucun sondage').first()).toBeVisible();
		await expect(page.getByRole('button', { name: /Nouveau sondage/ })).toHaveCount(ouvert ? 1 : 0);
	});
}
