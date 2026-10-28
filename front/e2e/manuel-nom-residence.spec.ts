/*
 *  **Le manuel porte le nom de la RÉSIDENCE, pas celui du logiciel.**
 *
 *  Demandé le 09/10/2026 : « les résidents ne connaissent pas CoproFirst, mais
 *  5Hostachy : oui ». Le manuel HTML est un fichier statique, servi tel quel à
 *  toutes les installations : son titre, l'en-tête du menu et son pied de page
 *  lisent le nom et le préfixe dans la configuration publique (`/api/config`),
 *  par un script de la page — « Manuel utilisateur — Résidence 5Hostachy ».
 *
 *  🔒 Le nom composé est celui du pied de page des écrans (`PiedDePage.svelte`) :
 *  le manuel ne peut pas importer `#lib/piedDePage`, alors le premier test rend
 *  LES DEUX sur la même configuration et les compare — une seconde façon de
 *  composer le nom divergerait sans que rien ne le dise.
 */
import { expect, simulerApi, test } from './aides';

const MANUEL = '/manuel-utilisateur.html';
const CONFIG = {
	site_nom: '5Hostachy',
	pied_de_page_prefixe_nom: 'Résidence',
	pied_de_page_ordre: 'residence',
};

test('le manuel dit « Résidence 5Hostachy », comme le pied de page des écrans', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => (chemin === '/api/config' ? CONFIG : undefined));

	await page.goto('/tableau-de-bord');
	const pied = page.locator('footer.app-footer .nom');
	await expect(pied).toHaveText(/^Résidence\s5Hostachy$/);
	const residence = (await pied.textContent())!.replace(/\u00a0/g, ' ').trim();

	await page.goto(MANUEL);
	await expect(page).toHaveTitle(`Manuel utilisateur — ${residence}`);
	await expect(page.locator('.sidebar-logo [data-nom-residence]')).toHaveText(residence);
	await expect(page.locator('.doc-footer [data-nom-residence]')).toHaveText(residence);
	//  Le logiciel n'est pas le nom que lit un résident : ni l'onglet, ni le menu.
	await expect(page.locator('.sidebar-logo')).not.toContainText('CoproFirst');
	await expect(page.locator('.hero')).not.toContainText('CoproFirst');
	await expect(page.locator('#apropos')).not.toContainText('CoproFirst');
});

test('sans préfixe réglé, le nom seul', async ({ page }) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/config' ? { ...CONFIG, pied_de_page_prefixe_nom: '' } : undefined,
	);
	await page.goto(MANUEL);
	await expect(page).toHaveTitle('Manuel utilisateur — 5Hostachy');
	await expect(page.locator('.sidebar-logo [data-nom-residence]')).toHaveText('5Hostachy');
});

test('configuration illisible : « Votre résidence », jamais un nom vide', async ({ page }) => {
	await page.route(
		(url) => url.pathname.startsWith('/api/'),
		(route) => route.fulfill({ status: 503, body: '' }),
	);
	await page.goto(MANUEL);
	await expect(page.locator('.sidebar-logo [data-nom-residence]')).toHaveText('Votre résidence');
	await expect(page.locator('.doc-footer [data-nom-residence]')).toHaveText('Votre résidence');
	await expect(page).toHaveTitle('Manuel utilisateur');
});
