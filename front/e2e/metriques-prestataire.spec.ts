/*
 *  **Les affaires traitées par un prestataire, en chiffres** (#1646) — sur sa
 *  fiche dépliée, pour le conseil seul.
 *
 *  Le serveur calcule tout (`test_metriques_affaires.py`). Ce que ce test tient :
 *
 *  1. rien n'est demandé tant que la fiche n'est pas dépliée ;
 *  2. dépliée : l'effectif, l'étape « Chez le prestataire » en jours ouvrés, les
 *     tuiles, et chaque exercice, le plus récent d'abord, qui se déplie sur ses
 *     affaires closes (R3d) ;
 *  3. sans affaire close, la fiche le dit — jamais « 0 j » ;
 *  4. au bureau comme au téléphone, la page ne défile pas en largeur.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal, elargirLeTexte } from './defilement';

const OTIS = {
	id: 1,
	nom: 'Ascenseurs Témoin',
	specialite: 'ascenseur',
	type_prestataire: 'maintenance_depannage',
	actif: true,
	archivee: false,
};

const resume = (nombre: number, chez: number | null, duree: number | null) => ({
	nombre,
	annulees: 0,
	duree_totale: duree,
	etapes: chez === null ? [] : [{ statut: 'chez_prestataire', jours: chez, nombre }],
	relances: nombre ? 1 : 0,
	//  Le serveur arrondit au dixième.
	relances_par_affaire: nombre ? Math.round(10 / nombre) / 10 : null,
	reaction_relance: null,
	reactions: 0,
	premiere_reponse_syndic: null,
	suites: null,
});

const METRIQUES = {
	prestataire_id: 1,
	ensemble: resume(3, 2, 3),
	exercices: [
		{
			annee: 2026,
			libelle: '2026',
			...resume(2, 2, 3),
			affaires: [
				{ id: 12, titre: 'Remplacement du barillet', cloture: '2026-11-12', issue: 'résolu' },
				{ id: 11, titre: 'Fuite sur le chauffe-eau', cloture: '2026-10-21', issue: 'annulé' },
			],
		},
		{
			annee: 2025,
			libelle: '2025',
			...resume(1, 2, 3),
			affaires: [{ id: 5, titre: 'Dépannage du portail', cloture: '2025-06-03', issue: 'résolu' }],
		},
	],
};

async function ouvrir(page: Page, metriques: object = METRIQUES) {
	const demandes: string[] = [];
	await simulerApi(page, (api) => {
		if (api === '/api/prestataires') return [OTIS];
		if (api === '/api/prestataires/1/metriques') return metriques;
	});
	page.on('request', (r) => {
		if (r.url().includes('/metriques')) demandes.push(r.url());
	});
	await page.goto('/prestataires');
	await attendreHydratation(page);
	return demandes;
}

async function deplier(page: Page) {
	const carte = page.locator('#presta-1');
	await carte.getByText('Ascenseurs Témoin').first().click();
	return carte;
}

test.beforeEach(async ({ page }, info) => {
	if (info.project.name === 'mobile') await page.setViewportSize({ width: 375, height: 812 });
});

test('rien n’est demandé avant de déplier la fiche', async ({ page }) => {
	const demandes = await ouvrir(page);
	await expect(page.locator('#presta-1')).toBeVisible(); //  cas zéro
	await expect(page.getByText('Affaires traitées')).toHaveCount(0);
	expect(demandes).toEqual([]);
});

test('dépliée : l’étape « Chez le prestataire », les tuiles et chaque exercice @mise-en-page', async ({
	page,
}) => {
	await ouvrir(page);
	const carte = await deplier(page);
	const bloc = carte.locator('section.metriques-presta');
	await expect(bloc).toContainText('Affaires traitées — conseil syndical');
	await expect(bloc).toContainText('3 affaires closes.');
	await expect(bloc).toContainText('Étape « Chez le prestataire » : 2 j en moyenne (jours ouvrés)');
	await expect(bloc.getByRole('list', { name: /Moyennes/ })).toContainText('Durée moyenne');

	//  Chaque exercice est un bouton, le plus récent d'abord ; replié, il ne montre pas ses affaires.
	const exercices = bloc.locator('.exercice-entete');
	await expect(exercices).toHaveCount(2);
	await expect(exercices.nth(0)).toContainText('2026');
	await expect(exercices.nth(1)).toContainText('2025');
	await expect(exercices.nth(0)).toHaveAttribute('aria-expanded', 'false');
	await expect(bloc.getByText('Remplacement du barillet')).toHaveCount(0); //  cas zéro

	//  Déplié : ses affaires, la plus récente d'abord, avec leur issue.
	await exercices.nth(0).click();
	await expect(exercices.nth(0)).toHaveAttribute('aria-expanded', 'true');
	const affaires = bloc.locator('.affaire');
	await expect(affaires.nth(0)).toContainText('Remplacement du barillet');
	await expect(affaires.nth(0)).toContainText('résolue');
	await expect(affaires.nth(1)).toContainText('Fuite sur le chauffe-eau');
	await expect(affaires.nth(1)).toContainText('annulée');

	await elargirLeTexte(page);
	await attendreSansDefilementHorizontal(page);
});

test('sans affaire close, la fiche le dit', async ({ page }) => {
	await ouvrir(page, {
		prestataire_id: 1,
		ensemble: resume(0, null, null),
		exercices: [],
	});
	const carte = await deplier(page);
	await expect(
		carte.getByText("Aucune affaire close où ce prestataire était l'intervenant désigné."),
	).toBeVisible();
	await expect(carte.locator('section.metriques-presta')).not.toContainText('0 j');
});
