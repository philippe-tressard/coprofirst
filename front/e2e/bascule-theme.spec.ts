/**
 *  La BASCULE du thème — Automatique, Clair, Sombre (mode sombre, #2174, lot S5).
 *
 *  `palette-sombre.spec.ts` juge la feuille sous un attribut posé à la main ;
 *  ce spec juge QUI le pose : le serveur, d'après le cookie `theme`
 *  (`hooks.server.ts`, `#lib/theme.ts`), et le sélecteur du Profil, qui
 *  l'applique sur place et le retient.
 *
 *  ## Aucun éclair : l'attribut est dans le HTML SERVI
 *
 *  Le HTML est lu par une requête, avant tout script : si l'attribut n'y était
 *  pas, le navigateur peindrait la page au clair puis la repeindrait. Les
 *  repères `%theme.…%` d'`app.html` ne doivent jamais partir en clair.
 */
import type { BrowserContext, Page } from '@playwright/test';
import { attendreHydratation, choisirPastille, expect, simulerApi, test } from './aides';

const SOMBRE = 'rgb(13, 27, 42)'; // --color-bg sombre, #0d1b2a
const CLAIR = 'rgb(242, 239, 233)'; // --color-bg clair, #f2efe9

async function poserCookie(context: BrowserContext, valeur: string) {
	await context.addCookies([
		{ name: 'theme', value: valeur, domain: '127.0.0.1', path: '/', sameSite: 'Lax' },
	]);
}

/** Ce que la page affiche : attribut, fond de la racine, balises du `<head>`. */
async function etat(page: Page) {
	return page.evaluate(() => {
		const racine = document.documentElement;
		const barres = [...document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')];
		return {
			attribut: racine.getAttribute('data-theme'),
			fond: getComputedStyle(racine).backgroundColor,
			schema: document.querySelector('meta[name="color-scheme"]')?.getAttribute('content'),
			barres: barres.map((m) => `${m.dataset.barre}:${m.media}`),
		};
	});
}

async function cookieTheme(context: BrowserContext) {
	return (await context.cookies()).find((c) => c.name === 'theme');
}

async function ouvrirConnexion(page: Page, systeme: 'light' | 'dark') {
	await page.emulateMedia({ colorScheme: systeme });
	await page.goto('/auth/connexion');
	await attendreHydratation(page);
}

async function ouvrirProfil(page: Page, systeme: 'light' | 'dark') {
	await page.emulateMedia({ colorScheme: systeme });
	await simulerApi(page);
	await page.goto('/profil');
	await attendreHydratation(page);
}

test.describe('Le HTML servi porte le thème', () => {
	for (const [cookie, attribut, schema] of [
		[null, 'auto', 'light dark'],
		['auto', 'auto', 'light dark'],
		['clair', 'light', 'light'],
		['sombre', 'dark', 'dark'],
		//  Liste blanche : une valeur inconnue retombe sur Automatique.
		['<script>', 'auto', 'light dark'],
	] as const) {
		test(`cookie ${cookie ?? 'absent'} → data-theme="${attribut}"`, async ({ page, context }) => {
			if (cookie !== null) await poserCookie(context, encodeURIComponent(cookie));
			const html = await (await page.request.get('/auth/connexion')).text();
			expect(html).toContain(`<html lang="fr" data-theme="${attribut}">`);
			expect(html).toContain(`<meta name="color-scheme" content="${schema}" />`);
			expect(html, 'aucun repère laissé en clair').not.toContain('%theme.');
		});
	}
});

test.describe('Le thème affiché', () => {
	test('sans cookie : Automatique, qui suit le système', async ({ page }) => {
		await ouvrirConnexion(page, 'dark');
		expect(await etat(page)).toMatchObject({ attribut: 'auto', fond: SOMBRE });
		await page.emulateMedia({ colorScheme: 'light' });
		expect((await etat(page)).fond).toBe(CLAIR);
	});

	test('Clair l’emporte sur un système sombre, barre comprise', async ({ page, context }) => {
		await poserCookie(context, 'clair');
		await ouvrirConnexion(page, 'dark');
		expect(await etat(page)).toMatchObject({
			attribut: 'light',
			fond: CLAIR,
			schema: 'light',
			barres: ['clair:all', 'sombre:not all'],
		});
	});

	test('Sombre l’emporte sur un système clair', async ({ page, context }) => {
		await poserCookie(context, 'sombre');
		await ouvrirConnexion(page, 'light');
		expect(await etat(page)).toMatchObject({
			attribut: 'dark',
			fond: SOMBRE,
			barres: ['clair:not all', 'sombre:all'],
		});
	});
});

test.describe('Le sélecteur du Profil', () => {
	test('ouvrir le Profil ne pose aucun cookie, et montre Automatique', async ({
		page,
		context,
	}) => {
		await ouvrirProfil(page, 'light');
		await expect(page.getByRole('radio', { name: /Automatique/ })).toBeChecked();
		expect(await cookieTheme(context)).toBeUndefined();
	});

	test('Sombre s’applique sur place, se retient, et tient au rechargement', async ({
		page,
		context,
	}) => {
		await ouvrirProfil(page, 'light');
		await choisirPastille(page, /Sombre/);
		expect(await etat(page)).toMatchObject({
			attribut: 'dark',
			fond: SOMBRE,
			schema: 'dark',
			barres: ['clair:not all', 'sombre:all'],
		});
		const cookie = await cookieTheme(context);
		expect(cookie).toMatchObject({ value: 'sombre', path: '/', sameSite: 'Lax' });
		//  Un an : la préférence ne se perd pas entre deux visites espacées.
		expect(cookie!.expires * 1000 - Date.now()).toBeGreaterThan(360 * 24 * 3600 * 1000);

		await page.reload();
		await attendreHydratation(page);
		expect((await etat(page)).attribut).toBe('dark');
		await expect(page.getByRole('radio', { name: /Sombre/ })).toBeChecked();
	});

	test('Clair sous un système sombre, puis retour à Automatique', async ({ page, context }) => {
		await ouvrirProfil(page, 'dark');
		expect((await etat(page)).fond).toBe(SOMBRE);
		await choisirPastille(page, /Clair/);
		expect(await etat(page)).toMatchObject({ attribut: 'light', fond: CLAIR, schema: 'light' });
		expect((await cookieTheme(context))?.value).toBe('clair');

		await choisirPastille(page, /Automatique/);
		expect(await etat(page)).toMatchObject({
			attribut: 'auto',
			fond: SOMBRE,
			schema: 'light dark',
			barres: ['clair:(prefers-color-scheme: light)', 'sombre:(prefers-color-scheme: dark)'],
		});
		expect((await cookieTheme(context))?.value).toBe('auto');
	});
});
