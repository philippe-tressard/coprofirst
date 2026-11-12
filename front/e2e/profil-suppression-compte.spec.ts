/*
 *  **Demander la suppression de son compte depuis le profil** (#2699).
 *
 *  Le même geste que l'app iOS (règle 5.1.1 v de l'App Store). Ce test tient ce
 *  que l'écran MONTRE et ce qui PART : les conséquences servies par l'API sont
 *  lues avant de confirmer, la confirmation exige le mot de passe, la charge
 *  porte le mot de passe et le motif, et une demande en cours se retire.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const CHEMIN = '/api/auth/demande-suppression';
const CONSEQUENCES = [
	'Votre compte et vos données personnelles sont effacés.',
	'Ce que vous avez écrit dans la vie collective reste, sans votre nom.',
];
const DEMANDE = {
	id: 4,
	statut: 'ouverte',
	cree_le: '2026-11-12T10:00:00',
	traitee_le: null,
	delai_annonce_jours: 30,
};

/** Ouvre le profil ; l'API simulée rend `etat()` à chaque lecture et note les écritures. */
async function ouvrirProfil(page: Page, etat: () => unknown) {
	const ecritures: { methode: string; corps: unknown }[] = [];
	await simulerApi(page);
	await page.route(
		(url) => url.pathname === CHEMIN,
		async (route) => {
			const requete = route.request();
			if (requete.method() === 'GET') {
				return route.fulfill({ status: 200, json: etat() });
			}
			ecritures.push({ methode: requete.method(), corps: requete.postDataJSON() });
			return requete.method() === 'POST'
				? route.fulfill({ status: 201, json: DEMANDE })
				: route.fulfill({ status: 204, body: '' });
		},
	);
	await page.goto('/profil');
	await attendreHydratation(page);
	return ecritures;
}

test('la demande montre ses conséquences, exige le mot de passe et part avec le motif', async ({
	page,
}) => {
	let demande: typeof DEMANDE | null = null;
	const ecritures = await ouvrirProfil(page, () => ({
		demande,
		delai_annonce_jours: 30,
		consequences: CONSEQUENCES,
	}));

	await page.getByRole('button', { name: 'Demander la suppression de mon compte' }).click();
	for (const phrase of CONSEQUENCES) await expect(page.getByText(phrase)).toBeVisible();
	const confirmer = page.getByRole('button', { name: 'Confirmer la demande' });
	await expect(confirmer).toBeDisabled();

	await page.getByLabel('Votre mot de passe, pour confirmer').fill('secret-du-titulaire');
	await page.getByLabel('Motif (facultatif)').fill('Je déménage');
	demande = DEMANDE;
	await confirmer.click();

	await expect(page.getByRole('button', { name: 'Retirer ma demande' })).toBeVisible();
	expect(ecritures).toEqual([
		{ methode: 'POST', corps: { mot_de_passe: 'secret-du-titulaire', motif: 'Je déménage' } },
	]);
});

test('une demande en cours se retire', async ({ page }) => {
	let demande: typeof DEMANDE | null = DEMANDE;
	const ecritures = await ouvrirProfil(page, () => ({
		demande,
		delai_annonce_jours: 30,
		consequences: CONSEQUENCES,
	}));

	await expect(page.getByText(/Demande de suppression envoyée le/)).toBeVisible();
	demande = null;
	await page.getByRole('button', { name: 'Retirer ma demande' }).click();

	await expect(
		page.getByRole('button', { name: 'Demander la suppression de mon compte' }),
	).toBeVisible();
	expect(ecritures.map((e) => e.methode)).toEqual(['DELETE']);
});
