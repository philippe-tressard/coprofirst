/*
 *  **Télémétrie : les gestes aboutis** (#1633).
 *
 *  Un formulaire ouvert puis envoyé envoie deux événements par la mesure
 *  d'audience — `click` à l'ouverture, `submit` à l'envoi réussi —, dont le
 *  `detail` est l'IDENTIFIANT du geste, jamais un contenu. L'onglet Télémétrie
 *  les rend par geste, avec le taux d'aboutissement, pour la liste FERMÉE de
 *  `#lib/aboutissement` : un geste déclaré s'affiche à zéro, un inconnu jamais.
 */
import {
	attendreHydratation,
	deplierSectionTelemetrie,
	type Evenement,
	expect,
	lotsEnvoyes,
	MEMBRE_CS,
	simulerApi,
	TABLEAU_TELEMETRIE_VIDE,
	test,
	viderLaFile,
} from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
const gestes = (recus: Evenement[]) =>
	recus.filter((e) => e.action === 'click' || e.action === 'submit');

test('ouvrir « Nouvelle affaire » compte une ouverture, sans rien de saisi', async ({ page }) => {
	await simulerApi(page);
	const recus = await lotsEnvoyes(page);
	await page.goto('/tickets');
	await attendreHydratation(page);

	//  Rien avant le geste : arriver sur la liste n'est pas ouvrir le formulaire.
	await viderLaFile(page);
	await expect.poll(() => recus.length).toBeGreaterThan(0);
	expect(gestes(recus)).toEqual([]);

	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();
	await viderLaFile(page);
	await expect
		.poll(() => gestes(recus))
		.toEqual([{ page: '/tickets', action: 'click', detail: 'affaire.creer' }]);
});

test('le panneau rend les gestes déclarés, leur taux, et tait un inconnu', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/telemetry/dashboard')
			return {
				...TABLEAU_TELEMETRIE_VIDE,
				gestes: [
					{ geste: 'affaire.creer', ouvertures: 8, envois: 2, taux: 25 },
					{ geste: 'inconnu.geste', ouvertures: 5, envois: 5, taux: 100 },
				],
			};
	});
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);
	const section = await deplierSectionTelemetrie(page, 'Gestes aboutis');

	await expect(
		section.getByRole('row', { name: /Créer une affaire\s+8\s+2\s+25 %/ }),
	).toBeVisible();
	//  Déclaré, jamais ouvert : à zéro, sans taux.
	await expect(section.getByRole('row', { name: /Voter à un sondage\s+0\s+0\s+—/ })).toBeVisible();
	await expect(section.getByText('inconnu.geste')).toHaveCount(0);
});

test('aucun formulaire ouvert : la section ne se déplie pas', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);
	const titre = page.getByRole('heading', { name: /Gestes aboutis/ });
	await expect(titre).toContainText('aucun formulaire ouvert');
});
