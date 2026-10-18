/*
 *  **Le lien de validation d'un compte rendu de point CS / Syndic** (#2042).
 *
 *  La page qu'ouvre un présent depuis le courriel, sans compte : elle montre le
 *  compte rendu et n'envoie RIEN à l'ouverture (`standards/03` §5 bis) ; seul
 *  « Je valide » valide. Les règles (tous les présents, 7 jours, commentaire qui
 *  suspend) sont tenues au serveur par `api/tests/test_points_conseil_validation.py`.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';
import type { CompteRenduParLien } from '../src/lib/api';

const CR: CompteRenduParLien = {
	etat: 'a_valider',
	debut: '2026-10-19T17:00:00',
	fin: null,
	a_distance: false,
	lieu: '1 rue Test',
	ou: 'Sur place — 1 rue Test',
	presents: ['Reine MARTIN', 'Paul BERNARD'],
	abordees: [
		{ numero: 'TK-000031', titre: 'Interphone muet', contenu: '<p>Devis <b>attendu</b>.</p>' },
	],
	non_traitees: ['TK-000040 Fuite colonne B'],
	deja_valide: false,
	echeance: '2026-10-26T15:00:00',
};

test('le lien montre le compte rendu sans rien valider, puis « Je valide » valide', async ({
	page,
}) => {
	const envois: string[] = [];
	page.on('request', (r) => {
		const url = new URL(r.url());
		if (url.pathname.startsWith('/api/points-conseil') && r.method() !== 'GET')
			envois.push(`${r.method()} ${url.pathname}`);
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/points-conseil/lien/abc') return CR;
		if (chemin === '/api/points-conseil/lien/abc/valider') return { ...CR, deja_valide: true };
		return undefined;
	});
	await page.goto('/point-cs/abc');
	await attendreHydratation(page);

	await expect(page.getByRole('heading', { name: 'TK-000031 · Interphone muet' })).toBeVisible();
	await expect(page.getByText('Devis attendu.')).toBeVisible();
	await expect(page.getByText('Non traitées : TK-000040 Fuite colonne B')).toBeVisible();
	await expect(page.getByText(/sera validé le 26 oct\. 2026/)).toBeVisible();
	//  L'ouverture n'a rien envoyé : un scanner de messagerie ne valide pas.
	expect(envois).toEqual([]);

	await page.getByRole('button', { name: 'Je valide' }).click();
	await expect(page.getByText('Merci : votre validation est enregistrée.')).toBeVisible();
	expect(envois).toEqual(['POST /api/points-conseil/lien/abc/valider']);
});

test('un lien inconnu le dit', async ({ page }) => {
	await simulerApi(page);
	//  Après `simulerApi` : Playwright essaie la route la plus récente d'abord.
	await page.route(
		(url) => url.pathname.startsWith('/api/points-conseil/lien/'),
		(route) =>
			route.fulfill({
				status: 404,
				contentType: 'application/json',
				body: JSON.stringify({ detail: 'Lien inconnu ou remplacé par un envoi plus récent' }),
			}),
	);
	await page.goto('/point-cs/perime');
	await attendreHydratation(page);
	await expect(page.getByText('Ce lien ne mène à aucun compte rendu')).toBeVisible();
});
