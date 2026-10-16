/*
 *  **Espace CS › Reporting › Suivi des affaires** (16/10/2026, maquette D2).
 *
 *  Toutes les affaires ni résolues ni annulées, relevées par le SERVEUR
 *  (`GET /suivi-affaires`) : l'écran ne fait que les montrer. L'API simulée rend
 *  donc la forme réelle du relevé — tranche d'ancienneté comprise —, et l'export
 *  PDF envoie au serveur la synthèse affichée.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';
import type { SuiviAffaires, SyntheseAffaires } from '../src/lib/api';

const RELEVE: SuiviAffaires = {
	jour: '2026-10-16',
	total: 3,
	anciennes: 1,
	synthese_disponible: true,
	par_categorie: [
		{ categorie: 'panne', libelle: 'Panne', nombre: 2 },
		{ categorie: 'etude_travaux', libelle: 'Étude & travaux', nombre: 1 },
	],
	affaires: [
		{
			id: 12,
			numero: 'TK-000012',
			titre: 'Ravalement de la façade nord',
			descriptif: 'Trois devis reçus, comparaison en cours par le conseil.',
			categorie: 'etude_travaux',
			libelle_categorie: 'Étude & travaux',
			statut: 'en_ag',
			libelle_statut: 'À l’AG',
			ouverte_le: '2026-03-16',
			age_jours: 214,
			anciennete: 'ancienne',
		},
		{
			id: 31,
			numero: 'TK-000031',
			titre: 'Interphone bâtiment C muet',
			descriptif: 'La platine de rue ne sonne plus.',
			categorie: 'panne',
			libelle_categorie: 'Panne',
			statut: 'en_cours',
			libelle_statut: 'Chez le syndic',
			ouverte_le: '2026-07-02',
			age_jours: 106,
			anciennete: 'ancienne',
		},
		{
			id: 40,
			numero: 'TK-000040',
			titre: 'Fuite colonne B',
			descriptif: '',
			categorie: 'panne',
			libelle_categorie: 'Panne',
			statut: 'ouvert',
			libelle_statut: 'Ouvert',
			ouverte_le: '2026-10-09',
			age_jours: 7,
			anciennete: 'recente',
		},
	],
};

const SYNTHESE: SyntheseAffaires = {
	resume: 'Trois affaires restent ouvertes, dont deux pannes.',
	points: ['Le ravalement attend l’AG.', 'Relancer le syndic pour l’interphone.'],
};

test('le suivi montre toutes les affaires ouvertes, leur nombre et leur répartition', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => (chemin === '/api/suivi-affaires' ? RELEVE : undefined));
	await page.goto('/espace-cs/reporting');
	await attendreHydratation(page);

	//  La première vue, sous son nouveau nom.
	await expect(page.getByRole('button', { name: /Suivi des affaires/ })).toBeVisible();
	const compteur = (libelle: string) =>
		page.locator('.kpi-card').filter({ has: page.getByText(libelle, { exact: true }) });
	await expect(compteur('affaires non fermées')).toContainText('3');
	await expect(compteur('de plus de 90 jours')).toHaveClass(/kpi-alert/);

	const barres = page.locator('.barres li');
	await expect(barres).toHaveCount(2);
	await expect(barres.nth(0)).toContainText('Panne');
	await expect(barres.nth(0)).toContainText('2');

	const lignes = page.locator('table.affaires tbody tr');
	await expect(lignes).toHaveCount(3);
	await expect(lignes.nth(0)).toContainText('214 j');
	await expect(lignes.nth(0)).toContainText('16 mars 2026');
	await expect(lignes.nth(0)).toContainText('Étude & travaux');
	await expect(lignes.nth(0).locator('.descriptif')).toHaveClass(/clamp-10/);
	await expect(lignes.nth(1).getByRole('link')).toHaveAttribute('href', '/tickets/31');
});

test('la synthèse de l’assistant part dans le PDF exporté', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/suivi-affaires') return RELEVE;
		if (chemin === '/api/suivi-affaires/synthese') return SYNTHESE;
		return undefined;
	});
	let corpsPdf: unknown = null;
	await page.route('**/api/suivi-affaires/pdf', (route) => {
		corpsPdf = route.request().postDataJSON();
		return route.fulfill({ status: 200, contentType: 'application/pdf', body: '%PDF-1.7' });
	});
	await page.goto('/espace-cs/reporting');
	await attendreHydratation(page);

	await page.getByRole('button', { name: /Rédiger la synthèse/ }).click();
	await expect(page.getByText(SYNTHESE.resume)).toBeVisible();
	await expect(page.getByRole('button', { name: /Relancer/ })).toBeVisible();

	const telechargement = page.waitForEvent('download');
	await page.getByRole('button', { name: /Exporter en PDF/ }).click();
	expect((await telechargement).suggestedFilename()).toBe('suivi-des-affaires-2026-10-16.pdf');
	expect(corpsPdf).toEqual({ synthese: SYNTHESE });
});

test('sans affaire ouverte, la vue le dit', async ({ page }) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/suivi-affaires'
			? { ...RELEVE, total: 0, anciennes: 0, par_categorie: [], affaires: [] }
			: undefined,
	);
	await page.goto('/espace-cs/reporting');
	await attendreHydratation(page);
	await expect(page.getByText('Aucune affaire ouverte')).toBeVisible();
});
