/*
 *  **Télémétrie : « Écrans non visités »** (#1630) — ce que personne n'a ouvert
 *  sur la période, pour décider quoi simplifier ou regrouper.
 *
 *  La comparaison est éprouvée à part (`npm run lint:ecrans-non-visites`) ; ici,
 *  le BLOC rendu : montré sur Mois et Année seulement, silencieux quand la période
 *  est vide (une absence de mesure n'est pas une mesure), et il marque comme
 *  « Réservé » l'écran qu'un rôle seul ouvre. L'API simulée rend toujours la
 *  portée qu'on lui fixe : c'est elle, et non la pastille cliquée, qui décide du bloc.
 */
import type { Page } from '@playwright/test';
import {
	attendreHydratation,
	expect,
	MEMBRE_CS,
	simulerApi,
	TABLEAU_TELEMETRIE_VIDE,
	test,
} from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

async function ouvrir(
	page: Page,
	scope: string,
	topPages: { page: string; total: number; uniques: number }[],
) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/telemetry/dashboard')
			return {
				...TABLEAU_TELEMETRIE_VIDE,
				scope,
				kpi: { vues: 12, utilisateurs: 3, pages: topPages.length },
				top_pages: topPages,
			};
	});
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);
}

const BLOC = (page: Page) => page.getByRole('heading', { name: /Écrans non visités/ });

const VUES = [
	{ page: '/tableau-de-bord', total: 8, uniques: 3 },
	{ page: '/tickets/', total: 4, uniques: 2 },
];

test('vue Mois : les écrans jamais ouverts sont listés, les ouverts non', async ({ page }) => {
	await ouvrir(page, 'mois', VUES);
	await expect(BLOC(page)).toBeVisible();
	const bloc = page.locator('.bloc', { has: BLOC(page) });
	//  L'accueil et la liste des affaires (visitée avec sa barre finale) ne sont pas listés.
	await expect(bloc.getByRole('cell', { name: '/tableau-de-bord', exact: true })).toHaveCount(0);
	await expect(bloc.getByRole('cell', { name: '/tickets', exact: true })).toHaveCount(0);
	//  Un écran que personne n'a ouvert l'est.
	await expect(bloc.getByRole('cell', { name: '/tickets/kanban', exact: true })).toBeVisible();
	await expect(bloc).toContainText('30 derniers jours');
});

test('vue Année : la période dit 12 derniers mois', async ({ page }) => {
	await ouvrir(page, 'annee', VUES);
	await expect(page.locator('.bloc', { has: BLOC(page) })).toContainText('12 derniers mois');
});

test('un écran réservé à un rôle est marqué « Réservé », pas présenté comme mort', async ({
	page,
}) => {
	await ouvrir(page, 'mois', VUES);
	const ligne = page.getByRole('row', { name: /\/espace-cs\b/ }).first();
	await expect(ligne).toContainText('Réservé');
	//  Un écran ouvert à tous ne porte pas la marque. `/avis` et non plus
	//  `/annonces`, fermée au syndic et au mandataire depuis #2075 (« Réservé »
	//  y est donc juste) : l'Avis est le seul onglet de la Communauté ouvert à tous.
	const ouverte = page
		.getByRole('row')
		.filter({ has: page.getByRole('cell', { name: '/avis', exact: true }) });
	await expect(ouverte).toHaveCount(1);
	await expect(ouverte).not.toContainText('Réservé');
});

test('vue Jour : le bloc se tait — presque tout écran y serait « non visité »', async ({
	page,
}) => {
	await ouvrir(page, 'jour', VUES);
	await expect(BLOC(page)).toHaveCount(0);
});

test('aucune page vue sur la période : pas de liste du site entier comme « mort »', async ({
	page,
}) => {
	await ouvrir(page, 'mois', []);
	await expect(BLOC(page)).toHaveCount(0);
});
