/*
 *  **Affaires : la liste se rend par paquets (#1840).**
 *
 *  96 cartes rendues d'un coup coûtaient +320 ms à un téléphone moyen après
 *  l'arrivée des données. Ce qu'on tient, sur cent affaires :
 *
 *  1. d'emblée, `PREMIERS` cartes seulement — et le compteur de la pastille
 *     retenue dit toujours CENT : il compte la liste, pas le rendu ;
 *  2. en descendant, la suite se rend, jusqu'à la dernière ;
 *  3. un lien profond vers une affaire lointaine l'ouvre quand même.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const TOTAL = 100;
const PREMIERS = 20; //  ⚠️ `PREMIERS` de `#lib/rendu-progressif`

const affaire = (id: number) => ({
	id,
	numero: `TK-2${String(id).padStart(4, '0')}`,
	titre: `Affaire ${id}`,
	description: 'Témoin',
	categorie: 'panne',
	natures: ['activite'],
	statut: 'ouvert',
	archivee: false,
	priorite: 'normale',
	perimetre_cible: [],
	auteur_id: 2,
	auteur_nom: 'Jean-Hervé KERBRAT',
	cree_le: '2026-10-01T10:00:00',
	mis_a_jour_le: '2026-10-01T10:00:00',
	photos_urls: [],
	fichiers_urls: [],
});

async function ouvrir(page: Page, adresse = '/tickets') {
	const affaires = Array.from({ length: TOTAL }, (_, i) => affaire(i + 1));
	await simulerApi(page, (chemin) => (chemin === '/api/tickets' ? affaires : undefined));
	await page.goto(adresse);
	await attendreHydratation(page);
}

const cartes = (page: Page) => page.locator('.carte-liste');

test('cent affaires : vingt cartes d’emblée, la suite en descendant', async ({ page }) => {
	await ouvrir(page);
	await expect(cartes(page)).toHaveCount(PREMIERS);
	//  Le compteur compte la LISTE, pas le rendu (`ux-patterns` §5).
	await expect(page.locator('.compte').first()).toHaveText(String(TOTAL));
	await expect
		.poll(async () => {
			await page.mouse.wheel(0, 20_000);
			return cartes(page).count();
		})
		.toBe(TOTAL);
});

test('un lien profond ouvre une affaire que le premier paquet ne rend pas', async ({ page }) => {
	await ouvrir(page, '/tickets?open=TK-20090');
	await expect(page.locator('#ticket-90.expanded')).toBeVisible();
});
