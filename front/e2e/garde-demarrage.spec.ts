/*
 *  **Une page qui ne se dessine pas se recharge, puis le dit** (#1993, 17/10/2026).
 *
 *  Signalé le 15/10/2026 : au premier chargement après trois MEP, la page de
 *  connexion d'un Chrome qui avait déjà la PWA est restée BLANCHE et figée ; le
 *  second chargement, une minute plus tard, était normal. Trois bancs — deux
 *  versions de production servies tour à tour, service worker de la première
 *  aux commandes, Chromium sans tête puis Chrome réel — ne l'ont pas reproduit :
 *  la cause exacte n'est pas établie.
 *
 *  Ce qui l'est, c'est le symptôme : une page rendue par le serveur qui reste
 *  blanche ne peut l'être que parce qu'une ressource qui BLOQUE le premier
 *  dessin (une feuille de style de `<head>`) ne répond pas — ou parce que le
 *  script de démarrage ne s'exécute pas. Ces tests le provoquent à coup sûr, à
 *  la place de l'aléa qu'on n'a pas su reproduire, et tiennent ce que la page
 *  doit faire alors : se recharger d'elle-même une fois, puis dire quoi faire.
 *  Jamais rester blanche sans un mot. Le garde vit dans `src/garde-demarrage.js`.
 */
import type { Page } from '@playwright/test';
import { expect, test } from './aides';

const FEUILLE_BLOQUEE = '/e2e-feuille-qui-ne-repond-pas.css';

/** Le premier dessin de contenu a-t-il eu lieu dans le document courant ? */
const dessinee = (page: Page) =>
	page
		.evaluate(() => performance.getEntriesByName('first-contentful-paint').length > 0)
		.catch(() => false); // document en cours de remplacement (rechargement)

/**
 * Sert `/auth/connexion` avec une feuille de style qui ne répond jamais, pour
 * les `n` premiers chargements du document : rien ne se dessine tant qu'elle
 * est attendue — c'est ainsi que Chrome traite une feuille de `<head>`.
 */
async function bloquerLeDessin(page: Page, chargements: number) {
	let restants = chargements;
	await page.route(
		(url) => url.pathname === '/auth/connexion',
		async (route) => {
			if (route.request().resourceType() !== 'document' || restants <= 0) {
				await route.continue();
				return;
			}
			restants--;
			const reponse = await route.fetch();
			const html = (await reponse.text()).replace(
				'</head>',
				`<link rel="stylesheet" href="${FEUILLE_BLOQUEE}"></head>`,
			);
			await route.fulfill({ response: reponse, body: html });
		},
	);
	//  Aucune réponse, jamais : la requête reste pendante comme celle du ticket.
	await page.route(`**${FEUILLE_BLOQUEE}`, () => {});
}

/**
 * Le module de l'application ne répond jamais : le HTML du serveur est là, mais
 * rien ne le fait fonctionner — l'application ne démarre pas.
 */
async function bloquerLeDemarrage(page: Page, chargements = Infinity) {
	let restants = chargements;
	await page.route('**/.svelte-kit/generated/client/app.js*', async (route) => {
		if (restants-- <= 0) await route.continue();
		//  sinon : aucune réponse, jamais
	});
}

/**
 * Les codes signalés au journal des erreurs du navigateur (`/api/telemetry/collect`).
 * La cause de #1993 n'est pas trouvée : chaque rechargement de secours se
 * MESURE, une fois, quand la page démarre ensuite (arbitrage du 17/10/2026).
 */
async function signalements(page: Page): Promise<string[]> {
	const codes: string[] = [];
	await page.route('**/api/telemetry/collect', async (route) => {
		const lot = route.request().postDataJSON() as { events: { action: string; detail?: string }[] };
		for (const e of lot.events) if (e.action === 'erreur' && e.detail) codes.push(e.detail);
		await route.fulfill({ status: 204 });
	});
	return codes;
}

const VERSION = String.raw`v\d+\.\d+\.\d+`;

test('Premier chargement jamais dessiné : la page se recharge d’elle-même et s’affiche', async ({
	page,
}) => {
	test.setTimeout(60_000);
	const codes = await signalements(page);
	await bloquerLeDessin(page, 1);
	await page.goto('/auth/connexion', { waitUntil: 'commit' });

	await expect
		.poll(() => dessinee(page), { timeout: 30_000, message: 'la page est restée blanche' })
		.toBe(true);
	await expect(page.locator('input#email')).toBeVisible();
	await expect(page.getByRole('alert')).toHaveCount(0);
	//  …et le rechargement de secours est signalé, une fois, avec la version servie.
	await expect.poll(() => codes).toHaveLength(1);
	expect(codes[0]).toMatch(new RegExp(`^garde-demarrage:non-dessinee:${VERSION}$`));
});

test('Toujours bloquée après le rechargement : la feuille en attente est lâchée, la page s’affiche', async ({
	page,
}) => {
	test.setTimeout(60_000);
	await bloquerLeDessin(page, 99);
	await page.goto('/auth/connexion', { waitUntil: 'commit' });

	await expect(page.locator('html[data-application="demarree"]')).toHaveCount(1, {
		timeout: 40_000,
	});
	await expect.poll(() => dessinee(page)).toBe(true);
	await expect(page.locator('input#email')).toBeVisible();
	await expect(page.getByRole('alert')).toHaveCount(0);
});

test('Toujours rien après le rechargement : la page le dit, et propose de recharger', async ({
	page,
}) => {
	test.setTimeout(60_000);
	await bloquerLeDessin(page, 99);
	await bloquerLeDemarrage(page);
	await page.goto('/auth/connexion', { waitUntil: 'commit' });

	const alerte = page.getByRole('alert');
	await expect(alerte).toContainText('Cette page ne s’affiche pas', { timeout: 40_000 });
	await expect(alerte.getByRole('button', { name: 'Recharger la page' })).toBeVisible();
	await expect.poll(() => dessinee(page)).toBe(true);
});

test('Dessinée mais jamais démarrée : la page le dit au lieu de rester figée', async ({ page }) => {
	test.setTimeout(60_000);
	const codes = await signalements(page);
	await bloquerLeDemarrage(page, 1);
	await page.goto('/auth/connexion', { waitUntil: 'commit' });

	const alerte = page.getByRole('alert');
	await expect(alerte).toContainText('L’application n’a pas fini de se charger', {
		timeout: 40_000,
	});
	//  Le bouton recharge ; la page démarre cette fois, et signale le motif.
	await alerte.getByRole('button', { name: 'Recharger la page' }).click();
	await expect(page.locator('html[data-application="demarree"]')).toHaveCount(1, {
		timeout: 20_000,
	});
	await expect(page.getByRole('alert')).toHaveCount(0);
	await expect.poll(() => codes).toHaveLength(1);
	expect(codes[0]).toMatch(new RegExp(`^garde-demarrage:non-demarree:${VERSION}$`));
});

test('Une page qui démarre normalement ne montre rien', async ({ page }) => {
	await page.goto('/auth/connexion');
	await expect(page.locator('html[data-application="demarree"]')).toHaveCount(1);
	await expect(page.getByRole('alert')).toHaveCount(0);
});
