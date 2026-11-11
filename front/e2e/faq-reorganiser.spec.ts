/*
 *  **Réorganiser la FAQ : l'ordre se change, s'enregistre, ou s'abandonne.**
 *
 *  Le mode « Réorganiser » a quitté `faq/+page.svelte` pour `ReorganisationFaq`
 *  le 28/09/2026 (#779, modularité). Un découpage ne change pas un
 *  comportement : ce test le vérifie sur le VRAI écran, API simulée, compte CS —
 *  ce qui part au serveur, ce que la page affiche ensuite, et le titre de
 *  catégorie passé par un slot, qui doit garder le style de la page.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const QUESTIONS = [
	{
		id: 1,
		categorie: 'Général',
		categorie_libelle: 'Général',
		question: 'Première question',
		reponse: '<p>a</p>',
		ordre: 0,
		actif: true,
	},
	{
		id: 2,
		categorie: 'Général',
		categorie_libelle: 'Général',
		question: 'Deuxième question',
		reponse: '<p>b</p>',
		ordre: 1,
		actif: true,
	},
	{
		id: 3,
		categorie: 'Tri des déchets',
		categorie_libelle: 'Tri des déchets',
		question: 'Où jeter le verre ?',
		reponse: '<p>c</p>',
		ordre: 0,
		actif: true,
	},
];

/** Les corps envoyés à `PATCH /api/faq/reorder`, dans l'ordre. */
async function ouvrir(page: Page): Promise<unknown[]> {
	const envois: unknown[] = [];
	page.on('request', (r) => {
		if (r.method() === 'PATCH' && new URL(r.url()).pathname === '/api/faq/reorder') {
			envois.push(r.postDataJSON());
		}
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/faq/all' || chemin === '/api/faq') return QUESTIONS;
		//  Le droit de rédiger est SERVI (#2654) : sans lui, pas de « Réorganiser ».
		if (chemin === '/api/faq/gestes') return { peut_rediger: true };
		if (chemin === '/api/faq/reorder') return null;
	});
	await page.goto('/faq');
	await attendreHydratation(page);
	await page.getByRole('button', { name: 'Réorganiser' }).click();
	return envois;
}

const lignes = (page: Page) => page.locator('.reorder-item .reorder-question');

test('descendre une question puis enregistrer envoie le nouvel ordre et referme', async ({
	page,
}) => {
	const envois = await ouvrir(page);

	//  Cas zéro : le mode est ouvert, avec ses trois lignes dans l'ordre reçu.
	await expect(lignes(page)).toHaveText([
		'Première question',
		'Deuxième question',
		'Où jeter le verre ?',
	]);

	//  Le titre de catégorie vient de la page par un slot : il garde SON style.
	const titre = page.locator('h2.categorie-title', { hasText: 'Général' });
	await expect(titre).toHaveCSS('text-transform', 'uppercase');

	await page.locator('.reorder-item').first().getByRole('button', { name: 'Descendre' }).click();
	//  La question descend DANS sa catégorie, et la catégorie reste à sa place :
	//  elle partait en bas de la liste jusqu'au 28/09/2026.
	await expect(lignes(page)).toHaveText([
		'Deuxième question',
		'Première question',
		'Où jeter le verre ?',
	]);

	await page.locator('.reorder-bar').getByRole('button', { name: 'Enregistrer' }).click();
	await expect(page.locator('.reorder-bar')).toHaveCount(0);
	await expect(page.getByRole('button', { name: 'Réorganiser' })).toBeVisible();

	//  Seules les deux questions déplacées partent, avec leur nouveau rang.
	expect(envois).toHaveLength(1);
	expect(envois[0]).toEqual(
		expect.arrayContaining([
			{ id: 2, ordre: 0 },
			{ id: 1, ordre: 1 },
		]),
	);
	expect((envois[0] as unknown[]).length).toBe(2);
});

test('annuler referme sans rien envoyer', async ({ page }) => {
	const envois = await ouvrir(page);
	await page.locator('.reorder-item').first().getByRole('button', { name: 'Descendre' }).click();
	await page.locator('.reorder-bar').getByRole('button', { name: 'Annuler' }).click();

	await expect(page.locator('.reorder-bar')).toHaveCount(0);
	expect(envois).toHaveLength(0);
});
