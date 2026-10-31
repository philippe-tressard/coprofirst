/*
 *  **La rangée de raccourcis de l'accueil — maquette A2** (#2397, 31/10/2026).
 *
 *  Arbitré à l'écran : Calendrier et Actualités n'étaient que des filtres de la
 *  page Affaires, et deux bandeaux pleine largeur redisaient la rangée. Ce que
 *  l'utilisateur VOIT désormais, et que ce fichier tient :
 *
 *  - Affaires porte, en second compteur, les affaires URGENTES ;
 *  - Calendrier montre le PROCHAIN rendez-vous (date, titre) et mène à SON
 *    affaire — sans rendez-vous, la pastille se tait ;
 *  - Actualités n'existe plus ;
 *  - « N relances » vit sur la pastille Espace CS, et le bandeau qui le redisait
 *    est parti ;
 *  - les consignes sont une pastille, au BOUT de la rangée.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const SANTE = {
	tickets_ouverts: 31,
	tickets_urgents: 2,
	sondages_actifs: 1,
	validations_cs: 0,
	validations_admin: 0,
	tickets_relance_syndic: 2,
	prochains: [],
};

async function accueil(page: Page, sante: Record<string, unknown>) {
	await simulerApi(page, (chemin) =>
		chemin === '/api/flux' ? { items: [], sante, delai_recent_jours: 30 } : undefined,
	);
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
	return page.getByRole('navigation', { name: 'Raccourcis' });
}

test('la rangée : urgentes sur Affaires, relances sur Espace CS, plus d’Actualités', async ({
	page,
}) => {
	const rangee = await accueil(page, SANTE);
	await expect(rangee.getByText('2 urgentes')).toBeVisible();
	await expect(rangee.getByRole('link', { name: '2 relances' })).toBeVisible();
	await expect(rangee.getByRole('link', { name: /Actualités/ })).toHaveCount(0);
	//  Le bandeau qui redisait la pastille est parti.
	await expect(page.getByText(/syndic à relancer/)).toHaveCount(0);
});

test('Calendrier montre le prochain rendez-vous et mène à son affaire', async ({ page }) => {
	const rangee = await accueil(page, {
		...SANTE,
		rendez_vous: { id: 42, titre: 'AG annuelle', debut: '2026-11-12T18:00:00', fin: null },
	});
	const lien = rangee.getByRole('link', { name: /Prochain rendez-vous : AG annuelle/ });
	await expect(lien).toHaveAttribute('href', '/tickets/42');
	await expect(lien).toContainText('12');
	await expect(lien).toContainText('AG annuelle');
});

test('sans rendez-vous, la pastille Calendrier se tait', async ({ page }) => {
	const rangee = await accueil(page, { ...SANTE, rendez_vous: null });
	await expect(rangee.getByRole('link', { name: /Affaires/ })).toBeVisible();
	await expect(rangee.getByRole('link', { name: /rendez-vous|Calendrier/ })).toHaveCount(0);
});

test('les consignes sont la DERNIÈRE pastille de la rangée', async ({ page }) => {
	const rangee = await accueil(page, SANTE);
	const derniere = rangee.getByRole('link').last();
	await expect(derniere).toHaveAccessibleName(/Consignes de la copropriété/);
	await expect(derniere).toHaveAttribute('target', '_blank');
});
