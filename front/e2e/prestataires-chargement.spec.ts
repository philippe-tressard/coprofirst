/*
 *  **Prestataires : ni deuxième vague, ni aller-retour au serveur (#1845).**
 *
 *  1. Les archives de l'onglet affiché partaient de l'`onMount` de l'onglet,
 *     qui ne se monte qu'une fois les trois listes de la page arrivées : une
 *     seconde vague, +130 ms à chaque ouverture. Ce test RETIENT la liste
 *     principale de l'onglet et vérifie que ses archives sont déjà demandées.
 *  2. La page portait le seul `+page.server.ts` des écrans applicatifs — une
 *     garde qui ne regardait que la présence d'un cookie. Son existence faisait
 *     demander `__data.json` au serveur à chaque navigation vers la page, et à
 *     chaque changement d'onglet, sans rien en tirer : le layout `(app)`
 *     renvoie à la connexion, et l'API refuse sans session (`hooks.server.ts`).
 *     Le test y vient d'un autre écran, SANS cookie, puis change d'onglet ; et
 *     le verrou : sans session, l'écran renvoie à la connexion avec son adresse.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, retenirApi, simulerApi, test } from './aides';

const PRESTATAIRE = {
	id: 1,
	nom: 'Otis',
	specialite: 'ascenseur',
	type_prestataire: 'maintenance_depannage',
};
const CONTRAT = {
	id: 11,
	prestataire_id: 1,
	copropriete_id: 1,
	type_equipement: 'ascenseur',
	libelle: 'Ascenseur',
	date_debut: '2025-01-01',
	perimetre_cible: ['résidence'],
	actif: true,
};

/** Simule l'API et note les chemins demandés — `__data.json` compris. */
async function simuler(page: Page) {
	const demandes: string[] = [];
	page.on('request', (r) => demandes.push(new URL(r.url()).pathname));
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/prestataires') return [PRESTATAIRE];
		if (chemin === '/api/prestataires/contrats') return [CONTRAT];
	});
	return demandes;
}

for (const [onglet, adresse, liste, archives] of [
	['Prestataires', '/prestataires', '/api/prestataires', '/api/prestataires/archives'],
	[
		'Contrats',
		'/prestataires/contrats',
		'/api/prestataires/contrats',
		'/api/prestataires/contrats/archives',
	],
]) {
	test(`${onglet} : les archives partent avec la liste, pas après`, async ({ page }) => {
		const demandes = await simuler(page);
		const relacher = await retenirApi(page, (chemin) => chemin === liste);
		await page.goto(adresse);
		//  Cas zéro : la liste est bien demandée — et toujours retenue.
		await expect.poll(() => demandes.includes(liste)).toBe(true);
		await expect.poll(() => demandes.includes(archives)).toBe(true);
		relacher();
	});
}

test('y venir d’un autre écran ne demande rien au serveur de pages', async ({ page }) => {
	const demandes = await simuler(page);
	await page.goto('/faq');
	await attendreHydratation(page);
	//  Un lien posé dans la page, et cliqué : le routeur de SvelteKit l'intercepte
	//  comme n'importe quel lien interne — c'est une navigation, pas un chargement.
	await page.evaluate(() => {
		const lien = document.createElement('a');
		lien.href = '/prestataires';
		document.body.append(lien);
		lien.click();
	});
	await expect(page.locator('#presta-1')).toBeVisible();
	await page
		.getByRole('tablist')
		.getByRole('link', { name: /Contrats/ })
		.click();
	await expect(page.locator('#contrat-11')).toBeVisible();
	//  Cas zéro : une NAVIGATION, pas un chargement — sinon rien n'est mesuré.
	expect(demandes.filter((d) => d === '/prestataires')).toEqual([]);
	expect(demandes.filter((d) => d.endsWith('__data.json'))).toEqual([]);
});

test('sans session, l’écran renvoie à la connexion et garde son adresse', async ({ page }) => {
	await simulerApi(page);
	//  Déclarée APRÈS `simulerApi` : la plus récente l'emporte.
	await page.route(
		(url) => url.pathname.startsWith('/api/auth/'),
		(route) => route.fulfill({ status: 401, contentType: 'application/json', body: '{}' }),
	);
	await page.goto('/prestataires/contrats');
	await expect(page).toHaveURL(/\/auth\/connexion\?next=%2Fprestataires%2Fcontrats$/);
});

test('« Nouveau contrat » cliqué avant l’arrivée de l’onglet ouvre quand même la création', async ({
	page,
}) => {
	//  L'onglet Contrats se charge au geste (#1844) : le bouton de l'en-tête
	//  appelait une méthode d'un onglet pas encore monté, et le clic se perdait.
	await simuler(page);
	let relacher: () => void = () => {};
	const relache = new Promise<void>((r) => (relacher = r));
	await page.route(
		(url) => url.pathname.endsWith('/OngletContrats.svelte'),
		async (route) => {
			await relache;
			await route.continue();
		},
	);
	await page.goto('/prestataires/contrats');
	await page.getByRole('button', { name: 'Nouveau contrat' }).click();
	relacher();
	await expect(page.getByRole('heading', { name: 'Nouveau contrat' })).toBeVisible();
});
