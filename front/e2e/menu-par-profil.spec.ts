/*
 *  **Le menu montre ce que le serveur ouvre au compte** (#2969, #2905).
 *
 *  Le syndic et le mandataire — rôle `externe`, ce que le serveur leur donne
 *  (`roles_du_statut`) — n'avaient AUCUNE entrée : le filtre de `Nav.svelte` ne
 *  connaissait que les rôles d'habitant. Le menu lit désormais `acces_menu`, servi
 *  par `/auth/me` ; le compte simulé le reçoit de `acces-menu-servis.json`, vérifié
 *  contre l'API. Le test compte les liens du menu latéral, pas des pixels.
 */
import type { Page } from '@playwright/test';
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const GENERALES = ['/tableau-de-bord', '/residence', '/tickets', '/mon-lot', '/annuaire', '/faq'];
const DU_CONSEIL = ['/prestataires', '/espace-cs'];

const lien = (page: Page, href: string) => page.locator(`nav.sidebar a.nav-item[href="${href}"]`);

async function ouvrirEnTantQue(page: Page, compte: Record<string, unknown>) {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? compte : undefined));
	await page.goto('/faq');
	//  Cas zéro : le menu est rendu.
	await expect(lien(page, '/faq')).toHaveCount(1);
}

for (const statut of ['syndic', 'mandataire']) {
	test(`le ${statut} a les pages générales et la Communauté, rien du conseil`, async ({ page }) => {
		await ouvrirEnTantQue(page, { ...MEMBRE_CS, statut, role: 'externe', roles: ['externe'] });
		for (const href of [...GENERALES, '/sondages']) await expect(lien(page, href)).toHaveCount(1);
		for (const href of [...DU_CONSEIL, '/delegations', '/admin'])
			await expect(lien(page, href)).toHaveCount(0);
	});
}

test('l’aidant a les pages générales et Délégations, pas la Communauté', async ({ page }) => {
	await ouvrirEnTantQue(page, {
		...MEMBRE_CS,
		statut: 'aidant',
		role: 'externe',
		roles: ['externe'],
	});
	for (const href of [...GENERALES, '/delegations']) await expect(lien(page, href)).toHaveCount(1);
	for (const href of [...DU_CONSEIL, '/sondages', '/admin'])
		await expect(lien(page, href)).toHaveCount(0);
});
