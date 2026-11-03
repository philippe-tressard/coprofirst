/*
 *  **Le logement de l'accueil vient du compte** (#2500, 03/11/2026).
 *
 *  « Bât. A, T3, 2ème » est nommé par le SERVEUR (`api/app/utils/logement.py`) et
 *  servi dans `GET /auth/me` (`libelle_logement`), que l'app iOS lit aussi.
 *  L'en-tête le rend tel quel : il ne recompose rien à partir des lots, qu'il ne
 *  demande d'ailleurs plus. Données fictives.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const enTete = (page: Page) => page.getByRole('heading', { level: 1 });

test('l’en-tête rend le libellé servi par le compte', async ({ page }) => {
	const lots: string[] = [];
	page.on('request', (r) => {
		if (new URL(r.url()).pathname === '/api/lots/mes-lots') lots.push(r.url());
	});
	await simulerApi(page, (chemin) =>
		chemin === '/api/auth/me' ? { ...MEMBRE_CS, libelle_logement: 'Bât. A, T3, 2ème' } : undefined,
	);
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
	await expect(enTete(page)).toContainText('Bât. A, T3, 2ème');
	expect(lots, 'l’accueil ne lit plus les lots pour nommer le logement').toEqual([]);
});

test('sans libellé, l’en-tête n’en invente pas', async ({ page }) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/auth/me' ? { ...MEMBRE_CS, libelle_logement: null } : undefined,
	);
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
	await expect(enTete(page)).toBeVisible();
	await expect(page.locator('.hero-lot-inline')).toHaveCount(0);
});
