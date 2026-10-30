/*
 *  **Le décor des jours de fête** (#2312) — ce que l'on VOIT, pas ce qu'on croit.
 *
 *  Un décor dans le coin des pages, les jours de fête seulement, si
 *  l'administration a activé le service (clé publique calculée `decor_fetes`
 *  de `GET /config`). Il passe derrière le contenu, ne capte aucun clic, et il
 *  est immobile si l'appareil demande moins d'animations.
 *
 *  L'horloge est fixée (`page.clock.setFixedTime`) : chaque date se rejoue,
 *  Pâques comprise, et le jour se lit à PARIS — 23 h 30 UTC le 28 octobre est
 *  déjà le 29 à Paris, premier jour d'Halloween.
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';

const DECOR = '.decor-fete';

async function ouvrirLe(page: Page, instant: string, actif = '1') {
	await page.clock.setFixedTime(new Date(instant));
	await simulerApi(page, (chemin) =>
		chemin === '/api/config' ? { site_nom: 'Résidence témoin', decor_fetes: actif } : undefined,
	);
	await page.goto('/tickets');
	//  Cas zéro : l'écran est rendu, le décor a eu le temps de se poser.
	await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

const JOURS: [string, string | null][] = [
	['2026-12-24T10:00:00+01:00', 'noel'],
	['2026-12-31T10:00:00+01:00', 'nouvel-an'],
	['2027-01-02T10:00:00+01:00', 'nouvel-an'],
	['2027-01-03T10:00:00+01:00', null],
	['2027-02-14T10:00:00+01:00', 'saint-valentin'],
	//  Pâques 2027 : dimanche 28 mars — du Vendredi saint (26) au lundi (29).
	['2027-03-25T10:00:00+01:00', null],
	['2027-03-26T10:00:00+01:00', 'paques'],
	['2027-03-29T10:00:00+02:00', 'paques'],
	['2027-03-30T10:00:00+02:00', null],
	//  2029 : le 1er avril EST le dimanche de Pâques — la fête d'un jour l'emporte.
	['2029-04-01T10:00:00+02:00', 'premier-avril'],
	['2029-03-31T10:00:00+02:00', 'paques'],
	['2027-06-21T10:00:00+02:00', 'fete-musique'],
	['2027-07-13T10:00:00+02:00', 'quatorze-juillet'],
	['2026-10-28T23:30:00Z', 'halloween'],
	['2026-10-28T21:30:00Z', null],
	['2026-11-05T10:00:00+01:00', null],
];

for (const [instant, fete] of JOURS) {
	test(`le ${instant} : ${fete ?? 'aucun décor'}`, async ({ page }) => {
		await ouvrirLe(page, instant);
		if (fete) await expect(page.locator(DECOR)).toHaveAttribute('data-fete', fete);
		else await expect(page.locator(DECOR)).toHaveCount(0);
	});
}

test('service coupé : aucun décor, même à Noël', async ({ page }) => {
	await ouvrirLe(page, '2026-12-24T10:00:00+01:00', '0');
	await expect(page.locator(DECOR)).toHaveCount(0);
});

test('le décor est un ornement : derrière, muet, à 25 %, sans capter de clic', async ({ page }) => {
	await ouvrirLe(page, '2026-12-24T10:00:00+01:00');
	const decor = page.locator(DECOR);
	await expect(decor).toHaveAttribute('aria-hidden', 'true');
	await expect(decor).toHaveCSS('pointer-events', 'none');
	await expect(decor).toHaveCSS('opacity', '0.25');
	await expect(decor).toHaveCSS('z-index', '-1');
	await expect(decor).toHaveCSS('position', 'fixed');
});

test('moins d’animations demandées : le décor reste, rien ne bouge', async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await ouvrirLe(page, '2026-12-24T10:00:00+01:00');
	await expect(page.locator(`${DECOR} .balance`)).toHaveCSS('animation-name', 'none');
});
