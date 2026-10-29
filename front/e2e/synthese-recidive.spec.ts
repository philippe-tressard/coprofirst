/*
 *  **Synthèse d'une affaire close : le bloc « La récidive »** (#1647) — le même
 *  équipement, déjà réparé sur le même périmètre dans les 24 mois.
 *
 *  Le serveur décide de tout : il calcule et fige le relevé, et le RETIRE pour qui
 *  n'est pas du conseil (`test_recidive_equipement.py`). L'écran ne fait que le
 *  dessiner quand il est là, et se taire quand il n'y est pas — c'est ce que ce
 *  test tient, sur le carnet (qui rend la même Suite que la fiche de l'affaire).
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';
import { attendreLisible, forcerTheme } from './contraste-ecran';

const METRIQUES = {
	version: 1,
	issue: 'résolu',
	ouverte_le: '2026-09-20T08:00:00',
	close_le: '2026-10-03T10:00:00',
	duree_totale: 9,
	premiere_reponse_syndic: 1,
	relances: 0,
	suites: 2,
	etapes: [{ statut: 'ouvert', jours: 9 }],
	etape_plus_longue: 'ouvert',
	reaction_relance: null,
	semaines: [1, 1],
	semaines_muettes: 0,
	chronologie: [],
	reouvertures: 0,
	comparaison: null,
};

const RECIDIVE = {
	equipement: 'ascenseur',
	mois: 24,
	autres: [
		{ id: 31, numero: 'TK-031', titre: 'Ascenseur bloqué au 3e', ferme_le: '2026-08-12T09:00:00' },
		{
			id: 17,
			numero: 'TK-017',
			titre: 'Porte palière de l’ascenseur',
			ferme_le: '2025-11-02T09:00:00',
		},
	],
};

async function ouvrir(page: Page, metriques: Record<string, unknown>) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return MEMBRE_CS;
		if (chemin === '/api/carnet-entretien')
			return {
				total: 1,
				entrees: [
					{
						date: '2026-10-03',
						libelle: 'Ascenseur en panne',
						origine: 'affaire',
						detail: '',
						categorie: 'panne',
						equipement: 'ascenseur',
						perimetre: ['bat:1'],
						lien: '/tickets/40',
						alerte: null,
						synthese: {
							id: 1,
							ticket_id: 40,
							evolution_id: 5,
							statut: 'validee',
							metriques,
							synthese: '<p>Récit.</p>',
							difficultes: null,
							amelioration: null,
							prompt_complement: null,
							assiste_ia: false,
							motif_vide: null,
							produite_le: '2026-10-03T10:30:00',
							validee_le: '2026-10-03T11:00:00',
							validee_par_nom: 'CS Témoin',
						},
					},
				],
			};
	});
	await page.goto('/residence/carnet');
	await attendreHydratation(page);
	await page.getByRole('button', { name: "Synthèse de l'affaire" }).click();
}

test('la récidive est dessinée : le constat, puis les autres affaires avec leurs liens', async ({
	page,
}) => {
	await ouvrir(page, { ...METRIQUES, recidive: RECIDIVE });
	//  Pliée avec la chronologie (maquette A, 15/10/2026) : on l'ouvre.
	const bloc = page.locator('details.plies');
	await bloc.locator('summary').click();
	await expect(bloc).toContainText('La récidive — le même équipement');
	//  Les deux autres, plus celle-ci : la troisième.
	await expect(bloc).toContainText('3ᵉ affaire résolue en 24 mois');
	await expect(bloc.getByRole('link', { name: 'TK-031' })).toHaveAttribute('href', '/tickets/31');
	await expect(bloc.getByRole('link', { name: 'TK-017' })).toHaveAttribute('href', '/tickets/17');
	await expect(bloc).toContainText('Ascenseur bloqué au 3e');
});

test('sans la clé, aucun bloc : le serveur la retire pour qui n’est pas du conseil', async ({
	page,
}) => {
	await ouvrir(page, METRIQUES);
	await expect(page.getByText('Les chiffres — durée')).toBeVisible();
	await expect(page.getByText('La récidive')).toHaveCount(0);
});

test('@sombre — la synthèse d’une affaire close : chiffres, frise, rythme et récidive se lit au thème sombre', async ({
	page,
}) => {
	await ouvrir(page, { ...METRIQUES, recidive: RECIDIVE });
	await page.locator('details.plies summary').click();
	await forcerTheme(page, 'sombre');
	//  Les marques du graphique sont claires exprès au sombre : mesurées à 3:1.
	await attendreLisible(page, '#contenu', { marques: '.segment, .semaine, .graphique-pastille' });
});
