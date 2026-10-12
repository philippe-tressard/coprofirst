/*
 *  **Qui vient, et combien de temps on attend un écran** (#1628, #1632, 03/10/2026).
 *
 *  Le tableau de bord ne donnait que des volumes. Ces tests tiennent les deux
 *  panneaux ajoutés — chaque taux avec ses deux nombres, les durées dans le
 *  format partagé — et la mesure elle-même : le navigateur poste la durée de la
 *  première page (`chargement`), celle d’un passage d’écran (`navigation`) et
 *  la fin d’affichage des données d’un écran de premier niveau (`donnees`, #1846).
 */
import {
	attendreHydratation,
	deplierSectionTelemetrie,
	expect,
	lotsEnvoyes,
	MEMBRE_CS,
	simulerApi,
	TABLEAU_TELEMETRIE_VIDE,
	test,
	viderLaFile,
} from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const ligne = (libelle: string, actifs: number, comptes: number, taux: number | null) => ({
	libelle,
	actifs,
	comptes,
	taux,
});

test('Qui vient : chaque taux porte ses deux nombres, et les refus sont dits', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/telemetry/dashboard')
			return {
				...TABLEAU_TELEMETRIE_VIDE,
				adoption: {
					periode: '30 derniers jours',
					global: ligne('Tous les comptes', 35, 61, 57),
					refus: 3,
					par_profil: [ligne('Résident', 18, 30, 60), ligne('Conseil syndical', 5, 6, 83)],
					par_type: [ligne('Copropriétaire résident', 14, 22, 64)],
					par_batiment: [ligne('Bât. A', 20, 31, 65)],
				},
			};
	});
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);

	const panneau = await deplierSectionTelemetrie(page, 'Qui vient');
	//  La période est celle de la VUE : le serveur la nomme, l'intitulé la porte.
	await expect(panneau.locator('summary')).toContainText('30 derniers jours');
	await expect(
		panneau.getByRole('row', { name: /Tous les comptes\s+35 \/ 61\s+57 %/ }),
	).toBeVisible();
	await expect(
		panneau.getByRole('row', { name: /Copropriétaire résident\s+14 \/ 22\s+64 %/ }),
	).toBeVisible();
	for (const groupe of ['Par profil', 'Par type de résident', 'Par bâtiment']) {
		await expect(panneau.getByRole('columnheader', { name: groupe })).toBeVisible();
	}
	await expect(panneau.getByText('3 comptes ont refusé la mesure d’audience')).toBeVisible();
});

test('Durées d’affichage : médiane et « 3 sur 4 » dans le format des durées', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/telemetry/dashboard')
			return {
				...TABLEAU_TELEMETRIE_VIDE,
				performance: {
					indicateurs: [{ indicateur: 'chargement', mesures: 12, mediane: 840, p75: 1250 }],
					pages: [
						{ page: '/tickets/#', indicateur: 'navigation', mesures: 4, mediane: 900, p75: 2300 },
					],
				},
			};
	});
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);

	const panneau = await deplierSectionTelemetrie(page, 'Durées d’affichage');
	await expect(
		panneau.getByRole('row', { name: /Ouverture du site\s+840 ms\s+1,3 s\s+12/ }),
	).toBeVisible();
	await expect(panneau.getByRole('row', { name: /\/tickets\/#.*2,3 s\s+4/ })).toBeVisible();
});

test('la première page et chaque passage d’écran postent leur durée', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	const recus = await lotsEnvoyes(page);
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);
	//  Un onglet est une adresse (`BarreOnglets`, des `<a>`) : le suivre est une
	//  navigation de l'application, pas un rechargement.
	await page.getByRole('link', { name: 'Utilisateurs', exact: true }).click();
	await expect(page).toHaveURL(/utilisateurs/);
	await viderLaFile(page);

	const durees = () => recus.filter((e) => e.action === 'perf').map((e) => e.detail ?? '');
	await expect.poll(durees).toContainEqual(expect.stringMatching(/^chargement:\d+$/));
	await expect.poll(durees).toContainEqual(expect.stringMatching(/^navigation:\d+$/));
	expect(recus.filter((e) => e.action === 'perf').every((e) => !/\d/.test(e.page))).toBe(true);
});

test('un écran de premier niveau poste ses données affichées, une fois (#1846)', async ({
	page,
}) => {
	await simulerApi(page);
	const recus = await lotsEnvoyes(page);
	await page.goto('/tickets');
	await attendreHydratation(page);
	//  Un onglet est une navigation : il ouvre un nouvel écran à mesurer, qui
	//  n'appelle pas la mesure — il ne doit rien produire, jamais 0.
	await page
		.getByRole('tablist')
		.getByRole('link', { name: /Kanban/ })
		.click();
	await expect(page).toHaveURL(/kanban/);
	await viderLaFile(page);

	const mesures = () => recus.filter((e) => e.action === 'perf');
	await expect
		.poll(() => mesures().map((e) => e.detail))
		.toContainEqual(expect.stringMatching(/^donnees:\d+$/));
	const donnees = mesures().filter((e) => e.detail?.startsWith('donnees:'));
	expect(donnees.map((e) => e.page)).toEqual(['/tickets']);
	//  Elle part du même instant que l'ouverture, et finit après l'hydratation.
	const valeur = (prefixe: string) =>
		Number(
			mesures()
				.find((e) => e.detail?.startsWith(prefixe))
				?.detail?.split(':')[1],
		);
	expect(valeur('donnees:')).toBeGreaterThanOrEqual(valeur('chargement:'));
});
