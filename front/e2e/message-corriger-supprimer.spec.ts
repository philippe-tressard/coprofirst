/*
 *  **Corriger ou retirer SON message** (14/11/2026, #2722/#2723) — et « Ajouter une
 *  suite » écrit en toutes lettres.
 *
 *  Demandé à l'écran : *« l'icône répondre et l'icône ajouter une suite sont trop
 *  confusantes ; j'ai par erreur fait répondre au lieu d'une suite »*, puis *« il
 *  n'est pas possible de supprimer ou modifier une réponse »*. Arbitré : l'AUTEUR
 *  corrige ou retire son message, tant que l'affaire n'est pas close.
 *
 *  - la carte porte un bouton « Ajouter une suite » avec son mot, plus une icône seule ;
 *  - sur sa propre bulle, d'une affaire ouverte : Modifier et Supprimer — pas sur celle
 *    d'un autre, pas sur une affaire close ;
 *  - Enregistrer envoie `PATCH /tickets/{id}/messages/{msg}` ; Supprimer, après
 *    confirmation, `DELETE`.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const affaire = (id: number, extra: Record<string, unknown> = {}) => ({
	id,
	numero: `TK-2091${id}`,
	titre: `Porte du hall ${id}`,
	description: '<p>Elle ne ferme plus.</p>',
	categorie: 'panne',
	statut: 'ouvert',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	nom_proprietaire: 'CS Témoin',
	categorie_libelle: 'Panne',
	statut_libelle: 'Ouvert',
	colonne_kanban: 'cs',
	urgente: false,
	close: false,
	peut_archiver: true,
	peut_changer_etat: true,
	peut_repondre: true,
	peut_modifier: false,
	peut_corriger: true,
	cree_le: '2026-11-10T10:00:00',
	mis_a_jour_le: '2026-11-10T10:00:00',
	perimetre_cible: [],
	photos_urls: [],
	fichiers_urls: [],
	...extra,
});

const OUVERTE = affaire(7);
const CLOSE = affaire(8, {
	statut: 'résolu',
	statut_libelle: 'Résolu',
	close: true,
	colonne_kanban: 'termine',
});

const message = (id: number, ticket: number, est_auteur: boolean, contenu: string) => ({
	id,
	ticket_id: ticket,
	auteur_id: est_auteur ? 1 : 2,
	auteur_nom: est_auteur ? 'CS Témoin' : 'Autre Témoin',
	est_auteur,
	contenu,
	interne: false,
	cree_le: '2026-11-12T10:00:00',
	fichiers_urls: [],
});

/** Les deux affaires simulées ; rend les corrections et les retraits reçus. */
async function simuler(page: Page) {
	const recu = { corrections: [] as unknown[], retraits: [] as string[] };
	await simulerApi(page, (chemin) => {
		const lu = [OUVERTE, CLOSE].find((t) => chemin === `/api/tickets/${t.id}`);
		if (lu) return lu;
	});
	//  Enregistrée APRÈS : Playwright essaie la dernière route d'abord.
	await page.route(
		(url) => /^\/api\/tickets\/[78]\/messages(\/\d+)?$/.test(url.pathname),
		(route) => {
			const { pathname } = new URL(route.request().url());
			const ticket = Number(pathname.split('/')[3]);
			const methode = route.request().method();
			const json = (corps: unknown, status = 200) =>
				route.fulfill({
					status,
					contentType: 'application/json',
					body: JSON.stringify(corps),
				});
			if (methode === 'GET')
				return json([
					message(ticket * 10 + 1, ticket, true, '<p>Toujours cassée.</p>'),
					message(ticket * 10 + 2, ticket, false, '<p>Vu, merci.</p>'),
				]);
			if (methode === 'PATCH') {
				const corps = route.request().postDataJSON() as { contenu: string };
				recu.corrections.push(corps);
				return json(message(ticket * 10 + 1, ticket, true, corps.contenu));
			}
			if (methode === 'DELETE') {
				recu.retraits.push(pathname);
				return route.fulfill({ status: 204 });
			}
			return route.fallback();
		},
	);
	return recu;
}

test('« Ajouter une suite » se lit sur la carte, avec son mot', async ({ page }) => {
	await simuler(page);
	await page.goto('/tickets/7');
	await attendreHydratation(page);

	const suite = page.locator('#ticket-7').getByRole('button', { name: 'Ajouter une suite' });
	await expect(suite).toBeVisible();
	await expect(suite).toContainText('Ajouter une suite');
});

test('sa propre bulle se corrige ; celle d’un autre, non', async ({ page }) => {
	const recu = await simuler(page);
	await page.goto('/tickets/7');
	await attendreHydratation(page);

	await expect(page.getByRole('button', { name: 'Modifier mon message' })).toHaveCount(1);
	await expect(page.getByRole('button', { name: 'Supprimer mon message' })).toHaveCount(1);

	await page.getByRole('button', { name: 'Modifier mon message' }).click();
	await page.locator('#msg-71 [contenteditable="true"]').fill('Réparée ce matin.');
	await page.getByRole('button', { name: 'Enregistrer' }).click();

	await expect.poll(() => recu.corrections.length).toBe(1);
	expect(JSON.stringify(recu.corrections[0])).toContain('Réparée ce matin.');
	await expect(page.locator('#msg-71')).toContainText('Réparée ce matin.');
});

test('retirer son message demande confirmation, puis l’API le supprime', async ({ page }) => {
	const recu = await simuler(page);
	await page.goto('/tickets/7');
	await attendreHydratation(page);

	await page.getByRole('button', { name: 'Supprimer mon message' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Supprimer' }).click();

	await expect.poll(() => recu.retraits).toEqual(['/api/tickets/7/messages/71']);
	await expect(page.locator('#msg-71')).toHaveCount(0);
});

test('une affaire close : plus de correction ni de retrait', async ({ page }) => {
	await simuler(page);
	await page.goto('/tickets/8');
	await attendreHydratation(page);

	await expect(page.locator('#msg-81')).toBeVisible();
	await expect(page.getByRole('button', { name: 'Modifier mon message' })).toHaveCount(0);
	await expect(page.getByRole('button', { name: 'Supprimer mon message' })).toHaveCount(0);
});
