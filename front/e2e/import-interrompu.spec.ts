/*
 *  **Une navigation pendant un `import()` ne lève aucune exception** (#2683, 11/11/2026).
 *
 *  La tranche WebKit de la CI tombait au hasard sur « TypeError: Importing a
 *  module script failed. », sans pile, au premier écran d'un worker. La cause,
 *  reproduite ici à coup sûr : un `import()` lancé sans destinataire —
 *  `virtual:pwa-register` (`MajDisponible`, 3 s après l'ouverture) et `dompurify`
 *  (`#lib/sanitize`) — est encore en vol quand le test navigue. WebKit interrompt
 *  le module et la page qui part lève une exception non rattrapée ; Chromium se
 *  tait. Sur un Vite froid, l'intervalle s'ouvre assez pour qu'un `page.goto`
 *  tombe dedans.
 *
 *  Le test RETIENT ces deux modules, navigue, puis les relâche : sans le
 *  rattrapage, le `test` des aides échoue sur l'exception de la page.
 *  🔒 `npm run lint:imports-rattrapes` refuse le prochain `import()` sans destinataire.
 */
import type { Route } from '@playwright/test';
import { attendreHydratation, test } from './aides';

/** Les modules chargés par un `import()` sans attente de l'écran : ceux qu'on retient. */
const RETENUS = /pwa-register|dompurify/;

test('naviguer pendant un import() en vol ne lève rien @moteur', async ({ page }) => {
	const retenues: Route[] = [];
	let pwaVu!: () => void;
	const pwaRetenu = new Promise<void>((r) => (pwaVu = r));
	await page.route(RETENUS, (route) => {
		retenues.push(route);
		if (/pwa-register/.test(route.request().url())) pwaVu();
	});

	await page.goto('/auth/connexion');
	//  `MajDisponible` charge le module au repos, après l'ouverture : on l'attend.
	await pwaRetenu;
	await page.goto('/auth/mot-de-passe-oublie');
	await attendreHydratation(page);

	//  Relâchées APRÈS la navigation : l'ancienne page n'est plus là pour les recevoir.
	for (const route of retenues) await route.abort().catch(() => {});
});
