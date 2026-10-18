/*
 *  **L'avis sur l'application : la note décide de ce que le formulaire demande** (#2075).
 *
 *  Sous 3 étoiles, « Ce qui vous a manqué » ; à partir de 4, la question de
 *  diffusion sur le site vitrine — Oui ou Non, AUCUNE réponse cochée d'office
 *  (une case pré-cochée n'est pas un consentement, arbitrage du 18/10/2026).
 *  Le serveur refuse l'avis sans réponse (`api/tests/test_avis.py`) ; ce test-ci
 *  vérifie ce que l'écran PROPOSE, et ce qu'il envoie une fois la réponse donnée.
 */
import type { Request } from '@playwright/test';
import { MEMBRE_CS, attendreHydratation, expect, simulerApi, test } from './aides';

const LISTE_VIDE = { avis: [], gestionnaire: false, mon_avis_id: null };

test('la note fait paraître la remarque puis la question, sans réponse d’office', async ({
	page,
}) => {
	const envois: Request[] = [];
	page.on('request', (r) => {
		if (r.method() === 'POST' && new URL(r.url()).pathname === '/api/avis') envois.push(r);
	});
	await simulerApi(page, (chemin) => (chemin === '/api/avis' ? LISTE_VIDE : undefined));

	await page.goto('/avis');
	await attendreHydratation(page);
	await page.getByRole('button', { name: '+ Donner mon avis' }).click();

	const remarque = page.getByLabel('Ce qui vous a manqué');
	const question = page.getByRole('radiogroup', { name: /publié sur coprofirst\.fr/ });
	await expect(remarque).toHaveCount(0);
	await expect(question).toHaveCount(0);

	await page.getByRole('button', { name: '2 sur 5' }).click();
	await expect(remarque).toBeVisible();
	await expect(question).toHaveCount(0);

	await page.getByRole('button', { name: '4 sur 5' }).click();
	await expect(remarque).toHaveCount(0);
	await expect(question).toBeVisible();
	//  🔴 Ni Oui ni Non : la réponse est à donner, jamais présumée.
	for (const nom of ['Oui', 'Non']) {
		await expect(question.getByRole('radio', { name: nom })).not.toBeChecked();
	}

	//  Le bouton radio est masqué sous sa pastille : on clique ce qu'on voit.
	await question.getByText('Non', { exact: true }).click();
	await expect(question.getByRole('radio', { name: 'Non' })).toBeChecked();
	await page.getByLabel('Titre').fill('Un site clair');
	await page.locator('.ProseMirror').first().fill('Tout se retrouve facilement.');
	await page.getByRole('button', { name: 'Enregistrer' }).click();

	await expect.poll(() => envois.length).toBe(1);
	const corps = envois[0].postDataJSON();
	expect(corps).toMatchObject({ note: 4, consentement_publication: false, remarque: null });
});

test('un problème renvoie vers une affaire « Bogue », pas vers un avis', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/avis' ? LISTE_VIDE : undefined));
	await page.goto('/avis');
	const lien = page.getByRole('link', { name: 'ouvrez une affaire' });
	await expect(lien).toHaveAttribute('href', '/tickets?nouveau=1&categorie=bug');
});

//  Arbitré le 18/10/2026 : l'Avis est la seule rubrique de la Communauté ouverte
//  au syndic. Les trois autres lui sont masquées, et leur adresse le ramène ici.
const SYNDIC = { ...MEMBRE_CS, statut: 'syndic', role: 'résident', roles: ['résident'] };

test('le syndic arrive sur l’Avis, seul onglet de la Communauté qui lui est ouvert', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return SYNDIC;
		if (chemin === '/api/avis') return LISTE_VIDE;
	});
	await page.goto('/sondages');
	await expect(page).toHaveURL(/\/avis$/);
	await expect(page.getByRole('link', { name: '⭐ Avis' })).toBeVisible();
	for (const nom of [/Sondages/, /Boîte à idées/, /Petites annonces/]) {
		await expect(page.getByRole('link', { name: nom })).toHaveCount(0);
	}
	await expect(page.getByRole('button', { name: '+ Donner mon avis' })).toBeVisible();
});
