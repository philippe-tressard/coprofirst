/*
 *  **L'opérateur qui n'est pas administrateur ouvre sa supervision, et elle seule (#2029).**
 *
 *  Admin se retire à un opérateur depuis le 16/10/2026 : il garde ses écrans,
 *  qui vivent sous `/admin`. L'écran doit donc :
 *  - lui offrir « Admin » au menu, et ne pas le renvoyer de `/admin` ;
 *  - ne lui montrer que les onglets `ouvertOperateur` (`#lib/onglets-ouverts`) —
 *    Installation, Maintenance, et Installations sur la référence : le seul
 *    groupe Exploitation (#2062) ;
 *  - ouvrir sa supervision sur l'adresse d'un autre onglet — comme toute clé
 *    inconnue de la page ouvre son premier onglet ;
 *  - ne rien demander que le serveur lui refuserait : ni les files d'« À traiter »,
 *    ni la configuration, ni la consommation de l'IA, ni l'export (données de la
 *    résidence, `require_admin`).
 */
import type { Page } from '@playwright/test';
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const OPERATEUR_SEUL = {
	...MEMBRE_CS,
	role: 'résident',
	roles: ['operateur', 'résident'],
};

/** Les lectures que le serveur réserve à l'administrateur. */
const RESERVEES_ADMIN = [
	'/api/admin/comptes-en-attente/enrichis',
	'/api/admin/utilisateurs',
	'/api/config/admin',
	'/api/config/textes-legaux',
	'/api/config/llm-consommation',
	'/api/admin/export-copropriete/dernier',
];

async function ouvrir(page: Page, adresse: string, moi = OPERATEUR_SEUL): Promise<string[]> {
	const lus: string[] = [];
	page.on('request', (r) => {
		const chemin = new URL(r.url()).pathname;
		if (chemin.startsWith('/api/')) lus.push(chemin);
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return moi;
		if (chemin === '/api/admin/installation')
			return { role: 'reference', libelle: 'Référence', branche: 'main', etat: 'non_verifie' };
	});
	await page.goto(adresse);
	return lus;
}

const onglet = (page: Page, nom: string) => page.locator('.tab-btn', { hasText: nom });

test('l’opérateur seul a « Admin » au menu et n’y voit que sa supervision', async ({ page }) => {
	const lus = await ouvrir(page, '/admin');
	await expect(page.locator('nav.sidebar a.nav-item[href="/admin"]')).toHaveCount(1);
	//  Cas zéro : la rangée est rendue, et elle est réduite — un seul groupe,
	//  donc pas de rangée de groupes (#2062).
	await expect(page.locator('.tab-btn.active')).toHaveText('Installation');
	await expect(onglet(page, 'Maintenance')).toBeVisible();
	await expect(onglet(page, 'Installations')).toBeVisible();
	await expect(onglet(page, 'Utilisateurs')).toHaveCount(0);
	await expect(page.locator('.groupe')).toHaveCount(0);
	//  La supervision est là ; ce qui porte des données de la résidence, non.
	await onglet(page, 'Maintenance').click();
	await expect(page.getByText('Contrôles de fiabilité').first()).toBeVisible();
	await expect(page.getByText('Export vérifié')).toHaveCount(0);
	expect(lus.filter((c) => RESERVEES_ADMIN.includes(c))).toEqual([]);
});

test('l’adresse d’un autre onglet lui ouvre sa supervision', async ({ page }) => {
	const lus = await ouvrir(page, '/admin?onglet=utilisateurs');
	await expect(page.locator('.tab-btn.active')).toHaveText('Installation');
	await expect(onglet(page, 'Utilisateurs')).toHaveCount(0);
	expect(lus.filter((c) => RESERVEES_ADMIN.includes(c))).toEqual([]);
});

test('témoin : l’opérateur administrateur, lui, lit ces données', async ({ page }) => {
	//  Sans ce témoin, une liste de chemins mal écrits passerait les deux tests
	//  ci-dessus sans rien prouver.
	const lus = await ouvrir(page, '/admin?onglet=maintenance', {
		...OPERATEUR_SEUL,
		role: 'admin',
		roles: ['admin', 'operateur'],
	});
	await expect(page.getByText('Export vérifié')).toBeVisible();
	await expect
		.poll(() => RESERVEES_ADMIN.filter((c) => c !== '/api/admin/utilisateurs' && !lus.includes(c)))
		.toEqual([]);
});
