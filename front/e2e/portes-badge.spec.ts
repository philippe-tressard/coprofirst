/*
 *  **Les portes d'un badge** — Espace CS › Badges & accès (#2217).
 *
 *  « Proposer, jamais poser » : les portes que les lots justifient s'affichent avec
 *  leur raison, ne cochent rien d'elles-mêmes, et ne partent dans la requête que si
 *  le conseil les REPREND — ce que l'écran montre est ce qui part. Les écarts entre
 *  les badges et leurs lots se lisent en tête du parc.
 *
 *  Lots, codes et comptes fictifs.
 */
import type { Page } from '@playwright/test';
import type { ChoixAcces, LotPourBadge, PorteProposee } from '../src/lib/api/acces';
import type { ConstatPatrimoine } from '../src/lib/api/etat-descriptif';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const LOTS: LotPourBadge[] = [
	{ id: 31, libelle: 'Lot 931', type: 'appartement', coproprietaire: null },
];
const CHOIX: Record<string, ChoixAcces> = {
	vigik: { codes: ['residence', 'bat:1', 'bat:4'], suit_le_lot: true },
	telecommande: { codes: [], suit_le_lot: false },
};
const PROPOSITION: PorteProposee[] = [
	{ code: 'bat:1', raison: 'votre logement' },
	{ code: 'bat:4', raison: 'dessert votre place' },
];
const CONSTATS: ConstatPatrimoine[] = [
	{
		code: 'badge_manque',
		gravite: 'avertissement',
		message: "Badge qui n'ouvre pas une circulation de ses lots.",
		lots: ['931'],
	},
];

async function ouvrir(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/acces/admin/choix-acces') return CHOIX;
		if (chemin === '/api/acces/admin/imports-lots') return LOTS;
		if (chemin.startsWith('/api/acces/admin/portes-proposees')) return PROPOSITION;
		if (chemin === '/api/acces/admin/constats-badges') return CONSTATS;
		if (chemin === '/api/acces/admin/vigik') return { id: 1, code: 'V-931' };
	});
	await page.goto('/espace-cs/badges');
	await attendreHydratation(page);
}

test('les écarts entre les badges et leurs lots se lisent en tête du parc', async ({ page }) => {
	await ouvrir(page);
	await expect(page.getByText('Écarts entre les badges et leurs lots')).toBeVisible();
	await expect(page.getByText("Badge qui n'ouvre pas une circulation de ses lots.")).toBeVisible();
});

test('la proposition ne coche rien : elle part seulement si le conseil la reprend', async ({
	page,
}) => {
	await ouvrir(page);
	await page.getByRole('button', { name: 'Enregistrer un accès' }).click();
	await page.locator('#acces-code').fill('V-931');
	await page.getByRole('combobox').filter({ hasText: '— aucun lot —' }).selectOption('31');
	await page.getByRole('button', { name: /^Accès/ }).click();

	const encart = page.locator('.proposition');
	await expect(encart).toContainText('dessert votre place');
	await expect(encart).toContainText('votre logement');

	await encart.getByRole('button', { name: 'Reprendre la proposition' }).click();
	await expect(encart.getByRole('button', { name: 'Proposition reprise' })).toBeDisabled();

	const envoi = page.waitForRequest(
		(r) => r.url().endsWith('/api/acces/admin/vigik') && r.method() === 'POST',
	);
	await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	const corps = (await envoi).postDataJSON();
	expect(corps.perimetre_cible).toEqual(['bat:1', 'bat:4']);
});

test('sans reprise, rien de la proposition ne part', async ({ page }) => {
	await ouvrir(page);
	await page.getByRole('button', { name: 'Enregistrer un accès' }).click();
	await page.locator('#acces-code').fill('V-932');
	await page.getByRole('combobox').filter({ hasText: '— aucun lot —' }).selectOption('31');
	await page.getByRole('button', { name: /^Accès/ }).click();
	await expect(page.locator('.proposition')).toContainText('dessert votre place');

	const envoi = page.waitForRequest(
		(r) => r.url().endsWith('/api/acces/admin/vigik') && r.method() === 'POST',
	);
	await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	const corps = (await envoi).postDataJSON();
	expect(corps.perimetre_cible ?? []).toEqual([]);
});
