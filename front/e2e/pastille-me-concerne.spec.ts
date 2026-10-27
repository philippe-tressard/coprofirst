/*
 *  **La pastille « Ce qui me concerne »** — liste des affaires et fil d'accueil (#2215).
 *
 *  Elle FILTRE ce que la liste montre déjà, d'après `me_concerne`, que le serveur
 *  pose sur chaque élément par la règle de l'accès : l'écran ne recompose rien.
 *  Ce qu'on lit :
 *  1. elle n'apparaît que s'il y a de quoi filtrer (« mes périmètres » non vides) ;
 *  2. retenue, elle ne garde que ce qui me concerne — et ce qui ne porte aucun lieu ;
 *  3. elle compte ce qu'elle montre (le standard des pastilles, maquette J).
 *
 *  Données fictives.
 */
import type { Page } from '@playwright/test';
import type { FluxItem, Ticket } from '../src/lib/api/types';
import type { MesPerimetres } from '../src/lib/api/patrimoine';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const affaire = (id: number, me_concerne: boolean | null) =>
	({
		id,
		numero: `TK-2215${id}`,
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
		cree_le: '2026-10-25T10:00:00',
		mis_a_jour_le: '2026-10-25T10:00:00',
		photos_urls: [],
		fichiers_urls: [],
		me_concerne,
	}) as unknown as Ticket;

const AFFAIRES = [affaire(1, true), affaire(2, false), affaire(3, null)];
const AVEC: MesPerimetres = { batiments: ['bat:1'], desservis: ['bat:4/ascenseur'] };
const SANS: MesPerimetres = { batiments: [], desservis: [] };

const rangee = (page: Page) => page.getByRole('group', { name: 'Portée', exact: true });

async function ouvrirAffaires(page: Page, mes: MesPerimetres) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return AFFAIRES;
		if (chemin === '/api/lots/mes-perimetres') return mes;
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
}

test('sans « mes périmètres », la pastille se tait', async ({ page }) => {
	await ouvrirAffaires(page, SANS);
	await expect(page.locator('[id^="ticket-"]')).toHaveCount(3);
	await expect(rangee(page)).toHaveCount(0);
});

test('retenue, elle garde ce qui me concerne et ce qui ne porte aucun lieu', async ({ page }) => {
	await ouvrirAffaires(page, AVEC);
	await expect(page.locator('[id^="ticket-"]')).toHaveCount(3);
	await rangee(page)
		.getByRole('button', { name: /Ce qui me concerne/ })
		.click();
	await expect(page.locator('[id^="ticket-"]')).toHaveCount(2);
	await expect(page.locator('#ticket-2')).toHaveCount(0);
	await expect(
		rangee(page)
			.getByRole('button', { name: /Ce qui me concerne/ })
			.locator('.compte'),
	).toHaveText('2');
});

const element = (id: string, titre: string, me_concerne: boolean | null): FluxItem => ({
	id,
	type: 'ticket_ouvert',
	date: '2026-10-25T09:00:00',
	cree_le: '2026-10-25T09:00:00',
	titre,
	badges: [],
	icon: '',
	meta: {},
	me_concerne,
});

test('le fil d’accueil filtre de la même façon', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/flux')
			return {
				items: [
					element('tk_1', 'Ascenseur de ma place', true),
					element('tk_2', 'Hall d’un autre bâtiment', false),
					element('ev_3', 'Assemblée générale', null),
				],
				sante: {},
				delai_recent_jours: 30,
			};
		if (chemin === '/api/lots/mes-perimetres') return AVEC;
	});
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
	await expect(page.getByText('Hall d’un autre bâtiment')).toBeVisible();
	await rangee(page)
		.getByRole('button', { name: /Ce qui me concerne/ })
		.click();
	await expect(page.getByText('Hall d’un autre bâtiment')).toHaveCount(0);
	await expect(page.getByText('Ascenseur de ma place')).toBeVisible();
	await expect(page.getByText('Assemblée générale')).toBeVisible();
});
