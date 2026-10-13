/*
 *  **Le compte technique de l'installation ne voit pas les outils du conseil.**
 *
 *  Signalé à l'écran le 13/10/2026 : l'administrateur créé à l'installation
 *  (admin seul — ni lot, ni conseil syndical) voyait « Prestataires » dans son
 *  menu. `Nav.svelte` le réservait à `$isCS`, qui INCLUT l'admin, quand
 *  l'Espace CS excluait déjà l'admin seul. Le manuel, lui, l'annonçait
 *  « Conseil syndical » : c'est le code qui divergeait.
 *
 *  Le test lit le menu de la barre latérale, rendu sur les deux profils (masqué
 *  par le style sur mobile) : il compte des liens, pas des pixels.
 */
import type { Page } from '@playwright/test';
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN_SEUL = {
	...MEMBRE_CS,
	prenom: 'Admin',
	statut: 'compte_technique',
	role: 'admin',
	roles: ['admin'],
};

const lien = (page: Page, href: string) => page.locator(`nav.sidebar a.nav-item[href="${href}"]`);

test('l’admin seul n’a ni Prestataires ni Espace CS au menu', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN_SEUL : undefined));
	await page.goto('/admin');
	//  Cas zéro : le menu est rendu, et c'est bien celui d'un admin.
	await expect(lien(page, '/admin')).toHaveCount(1);
	await expect(lien(page, '/prestataires')).toHaveCount(0);
	await expect(lien(page, '/espace-cs')).toHaveCount(0);
});

test('le membre du conseil garde Prestataires et l’Espace CS', async ({ page }) => {
	await simulerApi(page);
	await page.goto('/tableau-de-bord');
	await expect(lien(page, '/prestataires')).toHaveCount(1);
	await expect(lien(page, '/espace-cs')).toHaveCount(1);
});
