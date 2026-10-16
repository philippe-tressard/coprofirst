/*
 *  **Espace CS › Reporting › Suivi des affaires** (16/10/2026, maquette D2).
 *
 *  Toutes les affaires ni résolues ni annulées, relevées par le SERVEUR
 *  (`GET /suivi-affaires`) : l'écran ne fait que les montrer. L'API simulée rend
 *  donc la forme réelle du relevé — tranche d'ancienneté comprise —, et l'export
 *  PDF envoie au serveur la synthèse affichée.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';
import type { SuiviAffaires } from '../src/lib/api';

const RELEVE: SuiviAffaires = {
	jour: '2026-10-16',
	total: 3,
	anciennes: 1,
	resumes_disponibles: true,
	delai_jours: 30,
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
			perimetre_cible: [],
			jours_sans_avancee: 60,
			a_relancer: true,
			relances: ['2026-07-18', '2026-09-03'],
			//  Le résumé de l'assistant, montré à la place du descriptif (#2035).
			apercu: 'Le conseil compare trois devis avant le vote en AG.',
			apercu_ia: true,
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
			perimetre_cible: ['bâtiment C'],
			jours_sans_avancee: 40,
			a_relancer: true,
			relances: [],
			apercu: 'La platine de rue ne sonne plus.',
			apercu_ia: false,
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
			perimetre_cible: [],
			jours_sans_avancee: 7,
			a_relancer: false,
			relances: [],
			apercu: '',
			apercu_ia: false,
		},
	],
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
	//  Cinq lignes au plus, et le résumé de l'assistant se signale (#2035).
	await expect(lignes.nth(0).locator('.descriptif')).toHaveClass(/clamp-rapport/);
	await expect(lignes.nth(0).locator('.descriptif')).toContainText('compare trois devis');
	await expect(lignes.nth(0).locator('.ia-signe')).toBeVisible();
	await expect(lignes.nth(1).locator('.ia-signe')).toHaveCount(0);
	//  Le périmètre se dit, sauf celui par défaut (règle 4).
	await expect(lignes.nth(1)).toContainText('bâtiment C');
	await expect(lignes.nth(0).locator('.badge-perimetre')).toHaveCount(0);
	//  En mode Suivre, ni case ni colonne de relances : la maquette D2, telle quelle.
	await expect(page.locator('table.affaires input[type=checkbox]')).toHaveCount(0);
	await expect(lignes.nth(1).getByRole('link')).toHaveAttribute('href', '/tickets/31');
});

test('« Résumer les affaires » fait rédiger les résumés, puis les relit ; le PDF part sans synthèse', async ({
	page,
}) => {
	let resume = false;
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/suivi-affaires')
			return resume
				? {
						...RELEVE,
						affaires: RELEVE.affaires.map((a) =>
							a.id === 31 ? { ...a, apercu: 'Le syndic attend le devis.', apercu_ia: true } : a,
						),
					}
				: RELEVE;
		if (chemin === '/api/suivi-affaires/resumes') {
			resume = true;
			return { rediges: 3 };
		}
		return undefined;
	});
	let corpsPdf: unknown = null;
	await page.route('**/api/suivi-affaires/pdf', (route) => {
		corpsPdf = route.request().postDataJSON();
		return route.fulfill({ status: 200, contentType: 'application/pdf', body: '%PDF-1.7' });
	});
	await page.goto('/espace-cs/reporting');
	await attendreHydratation(page);

	//  La synthèse d'ensemble n'existe plus (#2035).
	await expect(page.getByText('Synthèse de l’assistant')).toHaveCount(0);
	await page.getByRole('button', { name: /Résumer les affaires/ }).click();
	const ligne = page.locator('table.affaires tbody tr').nth(1);
	await expect(ligne.locator('.descriptif')).toContainText('Le syndic attend le devis.');
	await expect(ligne.locator('.ia-signe')).toBeVisible();

	const telechargement = page.waitForEvent('download');
	await page.getByRole('button', { name: /Exporter en PDF/ }).click();
	expect((await telechargement).suggestedFilename()).toBe('suivi-des-affaires-2026-10-16.pdf');
	expect(corpsPdf).toEqual({});
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

test('relancer le syndic : la même liste, les relances envoyées, un pli et l’aperçu', async ({
	page,
}) => {
	let envoye: unknown = null;
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/suivi-affaires') return RELEVE;
		if (chemin === '/api/tickets/relance-syndic/reponses') return { reponses: [] };
		return undefined;
	});
	await page.route('**/api/tickets/relance-syndic', (route) => {
		envoye = route.request().postDataJSON();
		return route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({ sent: 2, relance_to: 'syndic@exemple.fr' }),
		});
	});
	//  L'adresse de l'alerte du tableau de bord : la relance est un MODE du suivi.
	await page.goto('/espace-cs/reporting?vue=relance');
	await attendreHydratation(page);

	await expect(page.getByRole('button', { name: 'Relancer le syndic' })).toHaveAttribute(
		'aria-pressed',
		'true',
	);
	await expect(page.getByRole('button', { name: /Relance syndic/ })).toHaveCount(0);

	//  À relancer : les deux affaires au-delà du délai, cochées, la plus ancienne en tête.
	const aRelancer = page.locator('section[aria-labelledby="titre-a-relancer"] tbody tr');
	await expect(aRelancer).toHaveCount(2);
	await expect(aRelancer.nth(0)).toContainText('Ravalement');
	await expect(aRelancer.locator('input[type=checkbox]:checked')).toHaveCount(2);
	//  Les relances déjà parties : leur nombre et leurs dates.
	await expect(aRelancer.nth(0)).toContainText('2 relances');
	await expect(aRelancer.nth(0)).toContainText('3 septembre');
	await expect(aRelancer.nth(1)).toContainText('aucune relance');

	//  Moins de 30 jours sans avancée : plié, rien de coché.
	const pli = page.getByRole('button', { name: /Moins de 30 jours sans avancée/ });
	await expect(pli).toHaveAttribute('aria-expanded', 'false');

	//  L'aperçu : les déjà relancées d'abord, avec le numéro de la relance qui part.
	const apercu = page.locator('section[aria-labelledby="titre-apercu-relance"]');
	await expect(apercu).toContainText('Déjà relancées — 1');
	await expect(apercu).toContainText('Relance n°3');
	await expect(apercu).toContainText('1ʳᵉ relance');

	//  Décocher une affaire la retire de l'aperçu et de l'envoi.
	await aRelancer.nth(1).locator('input[type=checkbox]').uncheck();
	await expect(apercu).not.toContainText('1ʳᵉ relance');
	await apercu.getByRole('button', { name: /Envoyer la relance \(1 affaire\)/ }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Confirmer' }).click();
	await expect.poll(() => envoye).toEqual({ ticket_ids: [12] });
});
