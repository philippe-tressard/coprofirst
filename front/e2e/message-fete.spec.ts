/*
 *  **Le message de fête** (#2312, proposition n° 3 du 30/10/2026) — à côté du
 *  décor, l'élément qui bouge s'arrête et le message apparaît là, environ toutes
 *  les 45 s, au plus tôt 8 s après le chargement. Rien en mouvement réduit, sur
 *  mobile, ni service coupé.
 *
 *  L'horloge est simulée (`page.clock.install`) : les minuteurs du cycle
 *  avancent à la demande, et le jour se lit à PARIS — 23 h 30 UTC le 31 décembre
 *  est déjà le 1er janvier, « Bonne année ».
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';
import { FETES, LONGUEUR_MAX_MESSAGE, messageDeFete } from '../src/lib/fetes';

const MESSAGE = '.decor-fete .message-fete';

async function ouvrirLe(page: Page, instant: string, actif = '1') {
	await page.clock.install({ time: new Date(instant) });
	await simulerApi(page, (chemin) =>
		chemin === '/api/config' ? { site_nom: 'Résidence témoin', decor_fetes: actif } : undefined,
	);
	await page.goto('/tickets');
	await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

/** Avance l'horloge par pas, jusqu'à ce que le message se montre — ou une minute. */
async function attendreMessage(page: Page): Promise<number> {
	const debut = await page.evaluate(() => Date.now());
	await expect
		.poll(
			async () => {
				await page.clock.runFor(250);
				return page.locator(`${MESSAGE}.visible`).count();
			},
			{ timeout: 60_000, intervals: [0] },
		)
		.toBe(1);
	return (await page.evaluate(() => Date.now())) - debut;
}

test('chaque fête a son message, assez court pour le coin', () => {
	for (const [code, { message }] of Object.entries(FETES)) {
		const textes = typeof message === 'string' ? [message] : message.map(([, t]) => t);
		expect(textes.length, code).toBeGreaterThan(0);
		for (const texte of textes) {
			expect(texte.trim(), code).not.toBe('');
			expect(texte.length, `${code} : « ${texte} »`).toBeLessThanOrEqual(LONGUEUR_MAX_MESSAGE);
		}
	}
});

test('le Nouvel an change de message au 1er janvier', () => {
	expect(messageDeFete('nouvel-an', '2026-12-29')).toBe('Bon réveillon');
	expect(messageDeFete('nouvel-an', '2026-12-31')).toBe('Bon réveillon');
	expect(messageDeFete('nouvel-an', '2027-01-01')).toBe('Bonne année');
	expect(messageDeFete('nouvel-an', '2027-01-02')).toBe('Bonne année');
	expect(messageDeFete('noel', '2026-12-24')).toBe('Joyeux Noël');
});

test('Halloween : le message se pose là où l’araignée s’arrête, pas avant 8 s', async ({
	page,
	isMobile,
}) => {
	test.skip(!!isMobile, 'aucun message sur mobile : test dédié plus bas');
	await ouvrirLe(page, '2026-10-30T10:00:00+01:00');
	const ecoule = await attendreMessage(page);
	expect(ecoule).toBeGreaterThanOrEqual(8_000);
	const message = page.locator(MESSAGE);
	await expect(message).toHaveText('Joyeux Halloween');
	await expect(message).toHaveCSS('pointer-events', 'none');
	//  À gauche de l'araignée arrêtée, à sa hauteur — mesuré une fois le fondu fini.
	await page.clock.runFor(300);
	const araignee = (await page.locator('.decor-fete .glisse').boundingBox())!;
	const bulle = (await message.boundingBox())!;
	expect(bulle.x + bulle.width).toBeLessThanOrEqual(araignee.x + araignee.width / 2);
	expect(Math.abs(bulle.y + bulle.height / 2 - (araignee.y + araignee.height / 2))).toBeLessThan(4);
	//  Muet et à l'opacité du décor : c'est lui qui l'enveloppe.
	await expect(page.locator('.decor-fete[aria-hidden="true"]')).toContainText('Joyeux Halloween');
	//  …puis il s'efface, et le cycle reprend.
	await expect
		.poll(async () => {
			await page.clock.runFor(500);
			return page.locator(`${MESSAGE}.visible`).count();
		})
		.toBe(0);
});

for (const [instant, texte] of [
	['2026-12-31T22:30:00Z', 'Bon réveillon'],
	['2026-12-31T23:30:00Z', 'Bonne année'],
] as const) {
	test(`le ${instant} (heure de Paris) : « ${texte} »`, async ({ page, isMobile }) => {
		test.skip(!!isMobile, 'aucun message sur mobile');
		await ouvrirLe(page, instant);
		await attendreMessage(page);
		await expect(page.locator(MESSAGE)).toHaveText(texte);
	});
}

/** Une minute et demie d'horloge : deux cycles au moins, et le décor est là. */
async function aucunMessage(page: Page) {
	await page.clock.runFor(90_000);
	await expect(page.locator(MESSAGE)).toHaveCount(0);
}

test('moins d’animations demandées : aucun message', async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await ouvrirLe(page, '2026-12-24T10:00:00+01:00');
	await expect(page.locator('.decor-fete')).toHaveAttribute('data-fete', 'noel');
	await aucunMessage(page);
});

test('service coupé : aucun message', async ({ page }) => {
	await ouvrirLe(page, '2026-12-24T10:00:00+01:00', '0');
	await aucunMessage(page);
});

test('mobile : le décor, sans message', async ({ page, isMobile }) => {
	test.skip(!isMobile, 'profil mobile seulement');
	await ouvrirLe(page, '2026-12-24T10:00:00+01:00');
	await expect(page.locator('.decor-fete')).toHaveAttribute('data-fete', 'noel');
	await aucunMessage(page);
});
