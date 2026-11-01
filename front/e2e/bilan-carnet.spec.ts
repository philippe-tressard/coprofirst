/*
 *  **Le bilan de l'exercice du carnet d'entretien** (#1645) — 📊, le conseil seul.
 *
 *  Le serveur calcule tout (`utils/synthese_affaire/agregats`, tenu par
 *  `test_metriques_affaires.py`). Ce que ce test tient, et qu'aucun contrôle de
 *  source ne verrait :
 *
 *  1. le bandeau n'est rendu qu'au conseil, replié, et ne demande RIEN au
 *     serveur avant d'être ouvert ;
 *  2. ouvert, il dit l'exercice et ses bornes, puis chaque catégorie : tuiles,
 *     temps par étape, intervenants les plus lents — en jours ouvrés, et « — »
 *     (jamais « 0 j ») là où rien ne se mesure ;
 *  3. une autre pastille d'exercice demande CET exercice ;
 *  4. un exercice sans affaire le dit ;
 *  5. au bureau comme au téléphone, la page ne défile pas en largeur.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';
import { attendreLisible, forcerTheme } from './contraste-ecran';
import { attendreSansDefilementHorizontal, elargirLeTexte } from './defilement';

const RESUME_VIDE = {
	annulees: 0,
	etapes: [],
	relances: 0,
	relances_par_affaire: null,
	reaction_relance: null,
	reactions: 0,
	premiere_reponse_syndic: null,
	suites: null,
};

const BILAN = {
	exercice: { annee: 2026, libelle: '2026', debut: '2026-01-01', fin: '2026-12-31' },
	exercices: [
		{ annee: 2026, libelle: '2026' },
		{ annee: 2025, libelle: '2025' },
	],
	nombre: 3,
	categories: [
		{
			...RESUME_VIDE,
			categorie: 'panne',
			nombre: 2,
			duree_totale: 4,
			etapes: [
				{ statut: 'ouvert', jours: 1.5, nombre: 2 },
				{ statut: 'chez_prestataire', jours: 2.5, nombre: 2 },
			],
			relances: 1,
			relances_par_affaire: 0.5,
			reaction_relance: 1,
			reactions: 1,
			premiere_reponse_syndic: 2,
			suites: 2.5,
			prestataires: [
				{ prestataire_id: 1, nom: 'Ascenseurs Témoin', jours: 3, nombre: 1 },
				{ prestataire_id: 2, nom: 'Plomberie Témoin', jours: 2, nombre: 1 },
			],
		},
		{
			...RESUME_VIDE,
			categorie: 'sinistre',
			nombre: 1,
			annulees: 1,
			duree_totale: 1,
			etapes: [{ statut: 'ouvert', jours: 1, nombre: 1 }],
			suites: 1,
			prestataires: [],
		},
	],
};

const PROPRIETAIRE = { ...MEMBRE_CS, role: 'propriétaire', roles: ['propriétaire'] };

async function ouvrir(page: Page, moi = MEMBRE_CS, bilan: object = BILAN) {
	const demandes: string[] = [];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return moi;
		if (chemin === '/api/carnet-entretien') return { entrees: [], total: 0 };
		if (chemin === '/api/carnet-entretien/metriques') return bilan;
	});
	page.on('request', (r) => {
		if (r.url().includes('/api/carnet-entretien/metriques')) demandes.push(r.url());
	});
	await page.goto('/residence/carnet');
	await attendreHydratation(page);
	return demandes;
}

test.beforeEach(async ({ page }, info) => {
	//  Le téléphone le plus étroit que le site s'engage à tenir.
	if (info.project.name === 'mobile') await page.setViewportSize({ width: 375, height: 812 });
});

test('le conseil voit le bandeau replié — et rien n’est demandé avant de l’ouvrir', async ({
	page,
}) => {
	const demandes = await ouvrir(page);
	const bandeau = page.getByRole('button', { name: /Bilan de l'exercice/ });
	await expect(bandeau).toBeVisible();
	await expect(bandeau).toHaveAttribute('aria-expanded', 'false');
	expect(demandes).toEqual([]);
});

test('un copropriétaire qui n’est pas du conseil ne voit pas le bilan', async ({ page }) => {
	const demandes = await ouvrir(page, PROPRIETAIRE);
	//  Cas zéro : le carnet, lui, est bien rendu.
	await expect(page.getByText('Ce que la copropriété a fait entretenir')).toBeVisible();
	await expect(page.getByRole('button', { name: /Bilan de l'exercice/ })).toHaveCount(0);
	expect(demandes).toEqual([]);
});

test('ouvert : l’exercice, puis chaque catégorie en jours ouvrés', async ({ page }) => {
	await ouvrir(page);
	await page.getByRole('button', { name: /Bilan de l'exercice/ }).click();

	await expect(page.getByText('Exercice 2026, du 1 janv. 2026 au 31 déc. 2026')).toBeVisible();
	await expect(page.getByText('3 affaires closes, dont 1 annulée')).toBeVisible();

	const panne = page.locator('section.bilan-categorie', { hasText: 'Panne' });
	await expect(panne.getByRole('heading')).toContainText('2 affaires closes');
	const tuiles = panne.getByRole('list', { name: /Moyennes/ });
	await expect(tuiles).toContainText('Durée moyenne');
	await expect(tuiles).toContainText('4 j');
	await expect(tuiles).toContainText('0,5 par affaire');
	await expect(
		panne.getByRole('columnheader', { name: 'Durée moyenne (jours ouvrés)' }).first(),
	).toBeVisible();
	await expect(panne.getByRole('row', { name: /Chez le prestataire/ })).toContainText('2,5 j');
	//  Les plus lents d'abord.
	const lents = panne.locator('table', { hasText: 'Intervenants les plus lents' });
	await expect(lents.getByRole('row').nth(1)).toContainText('Ascenseurs Témoin');
	await expect(lents.getByRole('row').nth(1)).toContainText('3 j');

	//  Sans relance : « — », jamais « 0 j ».
	const sinistre = page.locator('section.bilan-categorie', { hasText: 'Sinistre' });
	const reaction = sinistre.getByRole('listitem').filter({ hasText: 'Réaction après relance' });
	await expect(reaction).toContainText('—');
	await expect(reaction).not.toContainText('0 j');
	await expect(sinistre.locator('table', { hasText: 'Intervenants' })).toHaveCount(0);

	await elargirLeTexte(page);
	await attendreSansDefilementHorizontal(page);
});

test('une autre pastille demande cet exercice', async ({ page }) => {
	const demandes = await ouvrir(page);
	await page.getByRole('button', { name: /Bilan de l'exercice/ }).click();
	await expect(page.getByText('Exercice 2026,')).toBeVisible();
	const requete = page.waitForRequest((r) => r.url().includes('/metriques?exercice=2025'));
	await page.getByRole('group', { name: 'Exercice' }).getByRole('button', { name: '2025' }).click();
	await requete;
	expect(demandes[0]).not.toContain('exercice=');
});

test('un exercice sans affaire le dit', async ({ page }) => {
	await ouvrir(page, MEMBRE_CS, { ...BILAN, categories: [], nombre: 0 });
	await page.getByRole('button', { name: /Bilan de l'exercice/ }).click();
	await expect(
		page.getByText("Aucune affaire du carnet n'a été close sur l'exercice 2026."),
	).toBeVisible();
	await elargirLeTexte(page);
	await attendreSansDefilementHorizontal(page);
});

test('@sombre — le bilan de l’exercice du carnet d’entretien, déplié se lit au thème sombre', async ({
	page,
}) => {
	await ouvrir(page);
	await page.getByRole('button', { name: /Bilan de l'exercice/ }).click();
	await expect(page.getByText('3 affaires closes, dont 1 annulée')).toBeVisible();
	await forcerTheme(page, 'sombre');
	await attendreLisible(page, '#contenu');
});
