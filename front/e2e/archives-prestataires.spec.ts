/*
 *  **Prestataires et contrats : 📦 dans la liste, et un écran pour ce qu'on
 *  range (#1538, 02/10/2026).**
 *
 *  Le geste d'archivage était une corbeille 🗑️ intitulée « Archiver », sur la
 *  vue principale, et l'objet rangé n'avait plus d'écran : archiver revenait à
 *  supprimer sans le dire. `ux-patterns` §8 : 📦 dans la liste, la corbeille aux
 *  Archives seulement — et ces deux entités n'ont pas de suppression du tout.
 *
 *  Ce que le test tient, et qu'aucun contrôle de source ne verrait : la carte
 *  RENDUE n'offre que 📦, la section Archives existe et montre la fiche rangée
 *  avec son geste de retour, et 📦 envoie bien le geste unique `…/archivage`.
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';

const OTIS = {
	id: 1,
	nom: 'Otis',
	specialite: 'ascenseur',
	type_prestataire: 'maintenance_depannage',
	actif: true,
	archivee: false,
};
const RANGE = {
	id: 3,
	nom: 'Sicli',
	specialite: 'extincteurs',
	type_prestataire: 'maintenance_depannage',
	actif: false,
	archivee: true,
};
const contrat = (id: number, libelle: string, archivee: boolean) => ({
	id,
	prestataire_id: 1,
	copropriete_id: 1,
	type_equipement: 'ascenseur',
	libelle,
	date_debut: '2025-01-01',
	perimetre_cible: ['résidence'],
	actif: !archivee,
	archivee,
});

async function ouvrir(page: Page, chemin: string) {
	await simulerApi(page, (api) => {
		if (api === '/api/prestataires') return [OTIS];
		if (api === '/api/prestataires/archives') return [RANGE];
		if (api === '/api/prestataires/contrats') return [contrat(11, 'Ascenseur', false)];
		if (api === '/api/prestataires/contrats/archives')
			return [contrat(20, 'Ancien ascenseur', true)];
	});
	await page.goto(chemin);
}

test('annuaire : 📦 dans la liste, la fiche rangée aux Archives avec ↩️', async ({ page }) => {
	await ouvrir(page, '/prestataires');
	const carte = page.locator('#presta-1');
	await expect(carte).toBeVisible(); //  cas zéro

	//  📦 se DESSINE au trait depuis le 10/10/2026 (`IconeAction`, la page
	//  Affaires devenue le standard) : un pictogramme, aucun émoji.
	const archiver = carte.getByRole('button', { name: 'Archiver' });
	await expect(archiver.locator('.icone-action svg')).toHaveCount(1);
	await expect(archiver).toHaveText('');
	await expect(carte).not.toContainText('🗑');
	//  La fiche rangée ne s'affiche qu'une fois la section dépliée.
	await expect(page.locator('#presta-3')).toHaveCount(0);

	await page.getByRole('button', { name: /Archives/ }).click();
	const rangee = page.locator('#presta-3');
	await expect(rangee).toBeVisible();
	await expect(rangee.getByRole('button', { name: 'Restaurer' })).toBeVisible();
	await expect(rangee.getByRole('button', { name: 'Archiver' })).toHaveCount(0);
	await expect(rangee.getByRole('button', { name: 'Modifier' })).toHaveCount(0);
});

test('annuaire : 📦 demande confirmation, puis envoie le geste unique', async ({ page }) => {
	await ouvrir(page, '/prestataires');
	await page.locator('#presta-1').getByRole('button', { name: 'Archiver' }).click();

	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('Le prestataire « Otis » rejoindra les Archives.');
	const requete = page.waitForRequest(
		(r) => r.method() === 'PATCH' && r.url().endsWith('/api/prestataires/1/archivage'),
	);
	await boite.getByRole('button', { name: 'Archiver' }).click();
	expect((await requete).postDataJSON()).toEqual({ archivee: true });
});

test('contrats : 📦 dans la liste, le contrat rangé aux Archives avec ↩️', async ({ page }) => {
	await ouvrir(page, '/prestataires/contrats');
	const carte = page.locator('#contrat-11');
	await expect(carte).toBeVisible(); //  cas zéro
	const archiver = carte.getByRole('button', { name: 'Archiver' });
	await expect(archiver.locator('.icone-action svg')).toHaveCount(1);
	await expect(archiver).toHaveText('');
	await expect(carte).not.toContainText('🗑');

	await page.getByRole('button', { name: /Archives/ }).click();
	const range = page.locator('#contrat-20');
	await expect(range).toBeVisible();
	await expect(range.getByRole('button', { name: 'Restaurer' })).toBeVisible();
	await expect(range.getByRole('button', { name: 'Archiver' })).toHaveCount(0);
	//  Les décomptes d'échéance ne comptent que les contrats courants.
	await expect(page.getByText('1 contrat actif')).toBeVisible();
});
