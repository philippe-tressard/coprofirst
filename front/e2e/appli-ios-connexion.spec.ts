/**
 *  L'encart « application iPhone » de la page de connexion.
 *
 *  Un iPhone (ou un iPad) qui ouvre le site dans son navigateur se voit proposer
 *  l'application de l'App Store. Personne d'autre : ni l'ordinateur, ni Android,
 *  ni l'iPhone qui a déjà installé le site sur son écran d'accueil.
 *
 *  Les agents sont posés à la main, sous Chromium : c'est la LOGIQUE de choix qui
 *  est jugée (`#lib/appareil`), pas le moteur d'Apple.
 */
import type { Page } from '@playwright/test';
import { APPLI_IOS } from '../src/lib/plateforme';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const IPHONE =
	'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1';
//  Un iPad sous iPadOS 13+ se déclare Mac : seul l'écran tactile le distingue.
const IPAD_EN_MAC =
	'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15';
const MAC =
	'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15';
const ANDROID =
	'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36';

async function ouvrir(
	page: Page,
	reglages: { points?: number; ecranAccueil?: boolean } = {},
): Promise<void> {
	await simulerApi(page);
	await page.addInitScript((r) => {
		if (r.points !== undefined)
			Object.defineProperty(navigator, 'maxTouchPoints', { get: () => r.points });
		if (r.ecranAccueil) Object.defineProperty(navigator, 'standalone', { get: () => true });
	}, reglages);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);
}

const encart = (page: Page) => page.getByRole('complementary', { name: 'Application iPhone' });

test.describe('sur un iPhone', () => {
	test.use({ userAgent: IPHONE });

	test("l'encart propose l'App Store", async ({ page }) => {
		await ouvrir(page, { points: 5 });
		await expect(encart(page)).toBeVisible();
		await expect(encart(page).getByRole('link', { name: /App Store/ })).toHaveAttribute(
			'href',
			APPLI_IOS,
		);
	});

	test('« Plus tard » le retire, et il ne revient pas', async ({ page }) => {
		await ouvrir(page, { points: 5 });
		await encart(page).getByRole('button', { name: 'Plus tard' }).click();
		await expect(encart(page)).toHaveCount(0);
		await page.reload();
		await attendreHydratation(page);
		await expect(page.locator('form')).toBeVisible();
		await expect(encart(page)).toHaveCount(0);
	});

	test("rien depuis l'écran d'accueil : le site y est déjà installé", async ({ page }) => {
		await ouvrir(page, { points: 5, ecranAccueil: true });
		await expect(page.locator('form')).toBeVisible();
		await expect(encart(page)).toHaveCount(0);
	});
});

test.describe('sur un iPad qui se déclare Mac', () => {
	test.use({ userAgent: IPAD_EN_MAC });

	test("l'écran tactile le fait reconnaître", async ({ page }) => {
		await ouvrir(page, { points: 5 });
		await expect(encart(page)).toBeVisible();
	});
});

test.describe('ailleurs que sur un appareil Apple', () => {
	test('un Mac sans écran tactile ne voit rien', async ({ browser }) => {
		const contexte = await browser.newContext({ userAgent: MAC });
		const page = await contexte.newPage();
		await ouvrir(page, { points: 0 });
		await expect(page.locator('form')).toBeVisible();
		await expect(encart(page)).toHaveCount(0);
		await contexte.close();
	});

	test('Android ne voit rien', async ({ browser }) => {
		const contexte = await browser.newContext({ userAgent: ANDROID });
		const page = await contexte.newPage();
		await ouvrir(page, { points: 5 });
		await expect(page.locator('form')).toBeVisible();
		await expect(encart(page)).toHaveCount(0);
		await contexte.close();
	});
});
