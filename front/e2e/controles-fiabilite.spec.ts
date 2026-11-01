/*
 *  **Les contrôles de fiabilité se lisent dans l'onglet Maintenance.**
 *
 *  Jusqu'au 27/09/2026, les verdicts de `check-reliability.sh` (C1 à C30)
 *  n'allaient qu'à un journal et à des courriels : l'écran ne pouvait dire ni ce
 *  qui était en vigilance, ni si le contrôleur tournait. Ce test rend le VRAI
 *  onglet, API simulée, et lit ce qu'un administrateur voit :
 *
 *  - la ligne « Contrôles de fiabilité » de la synthèse, en « Points de
 *    vigilance » (orange) et non « À jour » ;
 *  - la carte qui liste, nœud par nœud, les constats EN COURS — le dernier
 *    rapport de chaque nœud, pas tous ;
 *  - aucune ligne qui déborde au doigt (profil mobile).
 */
import type { Page } from '@playwright/test';
import { expect, MEMBRE_CS, simulerApi, test } from './aides';
import { attendreLisible, forcerTheme } from './contraste-ecran';
import { attendreSansDefilementHorizontal } from './defilement';

//  La supervision technique est à l'OPÉRATEUR de la plateforme (#1750).
const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin', 'operateur'] };

const RAPPORTS = [
	{
		id: 3,
		noeud: 'rpi1',
		statut: 'avertissement',
		cree_le: '2026-09-27T14:06:00',
		details: {
			fail: 0,
			warn: 1,
			constats: [
				"[WARN] Noyaux DIVERGENTS — rpi1 en 6.12.62, rpi2 en 6.12.75 : les deux nœuds se relaient chaque nuit et ne se comportent pas pareil. Le dépôt archive.raspberrypi.com n'est pas dans les origines d'unattended-upgrades",
			],
		},
	},
	{
		id: 2,
		noeud: 'rpi2',
		statut: 'avertissement',
		cree_le: '2026-09-27T14:06:30',
		details: {
			fail: 0,
			warn: 1,
			constats: [
				"[WARN] Configuration apt ILLISIBLE sur rpi2 (1 erreur(s)) — apt-daily échoue chaque jour en silence, AUCUNE mise à jour n'arrive (#1377)",
			],
		},
	},
	//  Plus ancien : ne doit PAS s'afficher, la carte montre l'état courant.
	{
		id: 1,
		noeud: 'rpi1',
		statut: 'succes',
		cree_le: '2026-09-26T09:00:00',
		details: { fail: 0, warn: 0, constats: [] },
	},
];

const SANTE = {
	taches: [
		{
			tache: 'reliability',
			noeud: 'rpi2',
			noeuds: [
				{ noeud: 'rpi1', statut: 'vigilance', derniere: '2026-09-27T14:06:00' },
				{ noeud: 'rpi2', statut: 'vigilance', derniere: '2026-09-27T14:06:30' },
			],
			noeud_enregistre: true,
			statut: 'vigilance',
			derniere: '2026-09-27T14:06:30',
			noeud_en_retard: null,
			statut_en_retard: null,
		},
	],
	anomalies_recentes: [],
	anomalies_fenetre_jours: 7,
};

/** L'onglet Maintenance, avec les rapports de check-reliability donnés. */
async function ouvrir(page: Page, rapports: unknown) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/maintenance/sante') return SANTE;
		if (chemin === '/api/admin/maintenance/historique') return rapports;
		return undefined;
	});
	await page.goto('/admin?onglet=maintenance');
}

test('Maintenance : les constats de check-reliability, nœud par nœud', async ({ page }) => {
	await ouvrir(page, RAPPORTS);

	const carte = page.locator('section.config-section', {
		has: page.getByText('Contrôles de fiabilité', { exact: true }),
	});
	await expect(carte).toBeVisible();

	//  Le dernier rapport de CHAQUE nœud, et seulement lui.
	await expect(carte.getByText('RPI1', { exact: true })).toHaveCount(1);
	await expect(carte.getByText('RPI2', { exact: true })).toHaveCount(1);
	await expect(carte.getByText(/Configuration apt ILLISIBLE sur rpi2/)).toBeVisible();
	await expect(carte.getByText(/Noyaux DIVERGENTS/)).toBeVisible();
	await expect(carte.getByText('Tout est vert')).toHaveCount(0);
	//  Le préfixe technique cède la place à un badge lisible.
	await expect(carte.getByText('[WARN]', { exact: false })).toHaveCount(0);
	await expect(carte.locator('.constats .badge-orange', { hasText: /^Vigilance$/ })).toHaveCount(2);
	await expect(carte.locator('.noeud-entete .badge-orange')).toHaveText([
		'1 en vigilance',
		'1 en vigilance',
	]);

	//  La synthèse dit « Points de vigilance », pas « À jour ».
	await expect(
		page
			.locator('tr', { hasText: 'Contrôles de fiabilité' })
			.first()
			.getByText('Points de vigilance'),
	).toBeVisible();

	//  Rien ne déborde, au doigt comme à la souris.
	await attendreSansDefilementHorizontal(page, 'dans l’onglet Maintenance');

	await carte.screenshot({
		path: `test-results/controles-fiabilite-${test.info().project.name}.png`,
	});
});

/*
 *  #1396 — le 27/09/2026, « rapport de 17:06 » lu à 17:29 a fait croire le
 *  contrôleur mort, et chaque constat s'affichait deux fois, sous RPI1 et RPI2.
 *  Désormais : « dernier contrôle » (le battement) à côté de « constats depuis »,
 *  chaque constat UNE fois — sous le nœud qu'il nomme seul, ou sous « Les deux
 *  nœuds », dits par l'actif.
 */
const NOYAUX = '[WARN] Noyaux DIVERGENTS — rpi1 en 6.18.50, rpi2 en 6.12.75';
const APT = '[WARN] Listes apt périmées sur rpi2 : 162 j (seuil 7 j)';
const RAPPORTS_1396 = [
	{
		id: 5,
		noeud: 'rpi1',
		statut: 'avertissement',
		cree_le: '2026-09-27T15:06:00Z',
		terminee_le: '2026-09-27T15:36:00Z',
		details: { fail: 0, warn: 1, constats: [], communs: [NOYAUX], porte_communs: true },
	},
	{
		id: 4,
		noeud: 'rpi2',
		statut: 'avertissement',
		cree_le: '2026-09-27T15:06:30Z',
		terminee_le: '2026-09-27T15:36:30Z',
		details: { fail: 0, warn: 1, constats: [APT], communs: [], porte_communs: false },
	},
];

test('Maintenance : dernier contrôle, et chaque constat une seule fois (#1396)', async ({
	page,
}) => {
	await ouvrir(page, RAPPORTS_1396);
	const carte = page.locator('section.config-section', {
		has: page.getByText('Contrôles de fiabilité', { exact: true }),
	});
	await expect(carte).toBeVisible();

	//  Une fois chacun — c'était deux.
	await expect(carte.getByText(/Noyaux DIVERGENTS/)).toHaveCount(1);
	await expect(carte.getByText(/Listes apt périmées sur rpi2/)).toHaveCount(1);
	//  Le commun sous « Les deux nœuds », vu par l'actif.
	const communs = carte.locator('.noeud', { hasText: 'Les deux nœuds' });
	await expect(communs.getByText(/Noyaux DIVERGENTS/)).toBeVisible();
	await expect(communs.getByText(/vu par RPI1/)).toBeVisible();
	//  RPI1 n'a rien en propre : il est vert, le commun ne compte pas sous lui.
	await expect(
		carte.locator('.noeud', { hasText: 'RPI1' }).first().getByText('Tout est vert'),
	).toBeVisible();

	//  Les deux heures, et elles diffèrent : le battement n'a pas créé de rapport.
	const entete = carte.locator('.noeud-entete', { hasText: 'RPI2' });
	await expect(entete).toContainText('dernier contrôle');
	await expect(entete).toContainText('constats depuis');
	await expect(entete).toContainText('17:36');
	await expect(entete).toContainText('17:06');

	await carte.screenshot({
		path: `test-results/controles-fiabilite-1396-${test.info().project.name}.png`,
	});
});

test('@sombre — Admin › Maintenance : tâches planifiées et contrôles de fiabilité se lisent au thème sombre', async ({
	page,
}) => {
	await ouvrir(page, RAPPORTS);
	await expect(page.getByText('Contrôles de fiabilité', { exact: true })).toBeVisible();
	await forcerTheme(page, 'sombre');
	await attendreLisible(page, '#contenu');
});
