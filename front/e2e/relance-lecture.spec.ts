/*
 *  **Une lecture qui tombe pendant un redémarrage de l'API se rejoue une fois** (#1662).
 *
 *  Relevé en production le 03/10/2026 : `HTTP 503 /tickets` pendant la recréation
 *  du conteneur de l'API par un déploiement. Le résident lisait « Service
 *  momentanément indisponible » alors que, deux secondes plus tard, tout répondait.
 *
 *  Le client d'API (`#lib/api/client`) rejoue donc UNE fois, après une courte
 *  attente, un **GET** qui reçoit 502, 503 ou 504 — idempotent, donc sans risque.
 *  Jamais une écriture : rejouer un POST pourrait la faire deux fois.
 *
 *  Deux gestes, API simulée : la liste des sondages qui rend 503 puis 200 s'affiche
 *  sans erreur ; un vote sur une idée qui rend 503 n'est envoyé qu'UNE fois.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

const SONDAGE = {
	id: 7,
	question: 'Peinture du hall ?',
	description: null,
	cloture_le: null,
	cloture_forcee: false,
	resultats_publics: true,
	auteur_id: 1,
	cree_le: '2026-10-01T10:00:00',
	perimetre_cible: ['résidence'],
	public_cible: ['résidents'],
	nb_votants: 0,
	cloture: false,
	archivee: false,
	assiste_ia: false,
};

const IDEE = {
	id: 5,
	titre: 'Local vélos',
	description: '<p>À couvrir.</p>',
	auteur_id: 2,
	statut: 'ouverte',
	perimetre_cible: ['résidence'],
	public_cible: [],
	cree_le: '2026-10-01T10:00:00',
	nb_votes: 0,
	mon_vote: false,
	archivee: false,
	assiste_ia: false,
	reponses: [],
	nb_reponses: 0,
};

const INDISPONIBLE = {
	status: 503,
	contentType: 'application/json',
	body: JSON.stringify({ detail: 'Base de données temporairement indisponible' }),
};

test('un GET qui rend 503 puis 200 affiche la liste, sans erreur', async ({ page }) => {
	let appels = 0;
	await simulerApi(page);
	//  Après `simulerApi` : la route la plus récente prime.
	await page.route('**/api/sondages', (route) => {
		appels += 1;
		if (appels === 1) return route.fulfill(INDISPONIBLE);
		return route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify([SONDAGE]),
		});
	});

	await page.goto('/sondages');
	await attendreHydratation(page);

	await expect(page.getByText(SONDAGE.question)).toBeVisible({ timeout: 10_000 });
	expect(appels).toBe(2);
	await expect(page.getByText('Service momentanément indisponible')).toHaveCount(0);
});

test("un POST qui rend 503 n'est PAS rejoué", async ({ page }) => {
	let envois = 0;
	await simulerApi(page, (chemin) => (chemin === '/api/idees' ? [IDEE] : undefined));
	await page.route('**/api/idees/5/voter', (route) => {
		envois += 1;
		return route.fulfill(INDISPONIBLE);
	});

	await page.goto('/idees');
	await attendreHydratation(page);
	await page.getByTitle('Voter pour cette idée').click();

	await expect(page.getByText('Service momentanément indisponible')).toBeVisible();
	//  Plus longtemps que l'attente d'une relance : un rejeu aurait eu le temps de partir.
	await page.waitForTimeout(3000);
	expect(envois).toBe(1);
});
