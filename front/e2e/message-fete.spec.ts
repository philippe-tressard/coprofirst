/*
 *  **Le message de fête** (#2312, révision du 30/10/2026) — à sa place fixe sous
 *  le décor, alignée à droite, sans rien attendre du mouvement : environ toutes
 *  les 45 s, au plus tôt 8 s après le chargement, traversé d'un reflet à la
 *  couleur de la fête. Rien en mouvement réduit, sur mobile, ni service coupé.
 *
 *  L'horloge est simulée (`page.clock.install`) : les minuteurs du cycle
 *  avancent à la demande, et le jour se lit à PARIS — 23 h 30 UTC le 31 décembre
 *  est déjà le 1er janvier, « Bonne année ».
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';
import { FETES, LONGUEUR_MAX_MESSAGE, messageDeFete, type CodeFete } from '../src/lib/fetes';
import { REFLETS, degradeReflet } from '../src/lib/decor-fetes';

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

test('chaque fête a la couleur de son reflet', () => {
	const vues = new Map<string, CodeFete>();
	for (const code of Object.keys(FETES) as CodeFete[]) {
		expect(REFLETS[code].length, code).toBeGreaterThan(0);
		for (const c of REFLETS[code]) expect(c, code).toMatch(/^var\(--[\w-]+\)$/);
		expect(degradeReflet(code), code).toContain(REFLETS[code][0]);
		vues.set(REFLETS[code].join(), code);
	}
	//  Le 14 juillet passe ses trois couleurs ; Noël et le Nouvel an partagent l'or.
	expect(REFLETS['quatorze-juillet']).toHaveLength(3);
	expect(vues.size).toBe(Object.keys(FETES).length - 1);
});

test('Halloween : le message paraît à sa place, sous le décor, pas avant 8 s', async ({
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
	await expect(message).toHaveCSS('background-image', /linear-gradient/);
	//  Sous le décor, aligné à droite — mesuré une fois le fondu fini.
	await page.clock.runFor(300);
	const decor = (await page.locator('.decor-fete').boundingBox())!;
	const bulle = (await message.boundingBox())!;
	expect(bulle.y).toBeGreaterThanOrEqual(decor.y + decor.height);
	expect(bulle.x + bulle.width).toBeLessThanOrEqual(decor.x + decor.width);
	expect(decor.x + decor.width - (bulle.x + bulle.width)).toBeLessThan(20);
	//  Le reflet glisse : seule la position du dégradé change.
	const position = () => message.evaluate((e) => getComputedStyle(e).backgroundPosition);
	const avant = await position();
	await page.clock.runFor(1_500);
	await expect.poll(position).not.toBe(avant);
	//  Muet et à l'opacité du décor : c'est lui qui l'enveloppe.
	await expect(page.locator('.decor-fete[aria-hidden="true"]')).toContainText('Joyeux Halloween');
	//  …puis il s'efface, et le cycle reprend.
	await expect
		.poll(async () => {
			await page.clock.runFor(500);
			return page.locator(`${MESSAGE}.visible`).count();
		})
		.toBe(0);
	const second = await attendreMessage(page);
	expect(second).toBeGreaterThan(30_000);
});

test('le mouvement du décor arrêté : le message paraît quand même', async ({ page, isMobile }) => {
	test.skip(!!isMobile, 'aucun message sur mobile');
	await ouvrirLe(page, '2026-10-30T10:00:00+01:00');
	//  Le mouvement du décor arrêté, avant la première apparition : le message ne
	//  doit rien en attendre (la v3.40.0 attendait l'araignée, et se taisait).
	await page.addStyleTag({
		content: '.decor-fete [class]:not(.message-fete) { animation: none !important; }',
	});
	await expect(page.locator('.decor-fete .glisse')).toHaveCSS('animation-name', 'none');
	await attendreMessage(page);
	await expect(page.locator(MESSAGE)).toHaveText('Joyeux Halloween');
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
