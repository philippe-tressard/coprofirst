/*
 *  **L'édition d'une Suite corrige toutes ses sections — et d'abord son Suivi**
 *  (01/10/2026, demandé à l'écran).
 *
 *  La correction montait un formulaire nu : ni Suivi, ni Mise en avant, ni
 *  Destinataires. Elle passe désormais par le même composant que la Suite
 *  (`SuiteAffaire`), sans la Diffusion — la Suite est déjà partie.
 *
 *  La règle serveur (l'entrée corrigée à sa date, l'affaire seulement si c'est
 *  sa dernière transition) est tenue par `api/tests/test_correction_suite.py`.
 *  Ce test tient l'ÉCRAN et ce qu'il ENVOIE : l'état enregistré est la pastille
 *  active, et la pastille choisie part dans le `PATCH`.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, deplierEtape, expect, simulerApi, test } from './aides';

const AFFAIRE = {
	id: 7,
	numero: 'TK-124290',
	titre: 'Porte du hall bloquée',
	description: 'Elle ne se ferme plus.',
	categorie: 'panne',
	statut: 'en_cours',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	natures: ['activite'],
	cree_le: '2026-09-20T10:00:00',
	mis_a_jour_le: '2026-09-21T10:00:00',
};

const SUITE = {
	id: 31,
	ticket_id: 7,
	type: 'etat',
	contenu: '<p>Le serrurier passe jeudi.</p>',
	ancien_statut: 'ouvert',
	nouveau_statut: 'en_cours',
	statut_avant: 'ouvert',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	cree_le: '2026-09-21T10:00:00',
	fichiers_urls: [],
};

async function ouvrirLaCorrection(page: Page): Promise<unknown[]> {
	const envois: unknown[] = [];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets/7') return AFFAIRE;
		if (chemin === '/api/tickets/7/evolutions') return [SUITE];
	});
	//  Enregistrée APRÈS : Playwright essaie la dernière route d'abord.
	await page.route(
		(url) => url.pathname === '/api/tickets/7/evolutions/31',
		(route) => {
			envois.push(route.request().postDataJSON());
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify(SUITE),
			});
		},
	);
	await page.goto('/tickets/7');
	await attendreHydratation(page);
	await deplierEtape(page, 'La suite');
	await page.getByRole('button', { name: 'Modifier cette entrée' }).click();
	return envois;
}

test('la correction montre le Suivi enregistré, et pas la Diffusion', async ({ page }) => {
	await ouvrirLaCorrection(page);
	const formulaire = page.getByRole('group', { name: 'Modifier la suite' });
	await expect(formulaire.getByRole('button', { name: /Chez le syndic/ })).toHaveClass(/active/);
	await expect(formulaire.getByText('Suivi', { exact: true })).toBeVisible();
	await expect(formulaire.getByText('Diffusion', { exact: true })).toHaveCount(0);
});

test('la pastille choisie part dans la correction', async ({ page }) => {
	const envois = await ouvrirLaCorrection(page);
	const formulaire = page.getByRole('group', { name: 'Modifier la suite' });
	await formulaire.getByRole('button', { name: /Résolu/ }).click();
	await formulaire.getByRole('button', { name: 'Enregistrer' }).click();
	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0]).toMatchObject({ type: 'etat', nouveau_statut: 'résolu' });
	//  Aucun canal : une correction ne renvoie rien.
	expect(envois[0]).not.toHaveProperty('partager_whatsapp');
	expect(envois[0]).not.toHaveProperty('envoyer_syndic');
});

test('revenir à l’état d’avant en refait un commentaire', async ({ page }) => {
	const envois = await ouvrirLaCorrection(page);
	const formulaire = page.getByRole('group', { name: 'Modifier la suite' });
	await formulaire.getByRole('button', { name: /Ouvert/ }).click();
	await formulaire.getByRole('button', { name: 'Enregistrer' }).click();
	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0]).toMatchObject({ type: 'commentaire', nouveau_statut: null });
});
