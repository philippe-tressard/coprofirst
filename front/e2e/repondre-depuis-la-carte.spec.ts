/*
 *  **« Répondre » est sur la carte de l'affaire** (23/10/2026, demandé à l'écran).
 *
 *  Capture de la liste Affaires à l'appui : *« je ne vois pas l'icône répondre »*,
 *  puis *« cette icône doit être sur l'affaire »*. Le geste n'existait que sous le
 *  fil des messages de la page `/tickets/[id]`. L'icône rejoint la rangée de la
 *  carte (`ActionsTicket`), par la même règle (`gesteReponse`) :
 *
 *  - dans la LISTE, elle mène à la page de l'affaire, formulaire déjà ouvert et
 *    curseur dans le texte — c'est là que vivent le fil des messages et l'envoi ;
 *  - sur la page de l'affaire, elle ouvre ce formulaire sur place ;
 *  - l'envoi crée bien un message (`POST /tickets/{id}/messages`) ;
 *  - ↩️ « Rouvrir la discussion » sur une affaire close ; rien sur une actualité
 *    ni sur une affaire absorbée (#1704) ;
 *  - au téléphone (360 px), la rangée la plus longue — l'auteur au conseil :
 *    six icônes — laisse la place au titre et ne fait pas défiler la page.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal } from './defilement';

const affaire = (id: number, extra: Record<string, unknown> = {}) => ({
	id,
	numero: `TK-2090${id}`,
	titre: `Ascenseur en panne au bâtiment ${id}`,
	description: '<p>Bloqué au troisième.</p>',
	categorie: 'panne',
	statut: 'ouvert',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	cree_le: '2026-10-20T10:00:00',
	mis_a_jour_le: '2026-10-20T10:00:00',
	perimetre_cible: [],
	photos_urls: [],
	fichiers_urls: [],
	...extra,
});

//  Épinglée : le bouton d'options ne se montre que sur une option active —
//  c'est la rangée la plus longue, celle du test au téléphone.
const OUVERTE = affaire(7, { epingle: true });
const CLOSE = affaire(8, { statut: 'résolu' });
const ABSORBEE = affaire(9, { fusionnee: true });
const ACTUALITE = affaire(10, { categorie: 'actualite', natures: ['actualite'] });
const TOUTES = [OUVERTE, CLOSE, ABSORBEE, ACTUALITE];

/** La liste et la page de l'affaire 7 simulées ; rend les messages postés. */
async function simuler(page: Page): Promise<unknown[]> {
	const envois: unknown[] = [];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return TOUTES;
		const lu = TOUTES.find((t) => chemin === `/api/tickets/${t.id}`);
		if (lu) return lu;
	});
	//  Enregistrée APRÈS : Playwright essaie la dernière route d'abord.
	await page.route(
		(url) => url.pathname === '/api/tickets/7/messages',
		(route) => {
			if (route.request().method() !== 'POST') return route.fallback();
			envois.push(route.request().postDataJSON());
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					id: 90,
					ticket_id: 7,
					contenu: '<p>Toujours bloqué ce matin.</p>',
					interne: false,
					cree_le: '2026-10-23T10:00:00',
					fichiers_urls: [],
				}),
			});
		},
	);
	return envois;
}

const icone = (page: Page, id: number, nom: string) =>
	page.locator(`#ticket-${id}`).getByRole('button', { name: nom, exact: true });

test('l’icône est sur la carte de la liste, selon l’affaire', async ({ page }) => {
	await simuler(page);
	await page.goto('/tickets');
	await attendreHydratation(page);

	await expect(icone(page, 7, 'Répondre')).toBeVisible();
	await expect(icone(page, 7, 'Répondre')).toHaveAttribute('title', 'Répondre');
	//  Absorbée : la discussion vit dans la principale. Actualité : elle informe.
	await expect(page.locator('#ticket-9')).toBeVisible();
	await expect(icone(page, 9, 'Répondre')).toHaveCount(0);
	await expect(icone(page, 9, 'Rouvrir la discussion')).toHaveCount(0);
	await expect(page.locator('#ticket-10')).toBeVisible();
	await expect(icone(page, 10, 'Répondre')).toHaveCount(0);
});

test('une affaire close : ↩️ « Rouvrir la discussion », comme sous le fil', async ({ page }) => {
	await simuler(page);
	await page.goto('/tickets/8');
	await attendreHydratation(page);

	await expect(icone(page, 8, 'Rouvrir la discussion')).toBeVisible();
	await expect(icone(page, 8, 'Répondre')).toHaveCount(0);
	await expect(page.locator('.carte-repondre')).toContainText('Rouvrir la discussion');
});

test('depuis la liste : la page de l’affaire, formulaire ouvert, et l’envoi crée le message', async ({
	page,
}) => {
	const envois = await simuler(page);
	await page.goto('/tickets');
	await attendreHydratation(page);

	await icone(page, 7, 'Répondre').click();
	await expect(page).toHaveURL(/\/tickets\/7\?repondre=1$/);
	const formulaire = page.getByRole('group', { name: 'Répondre' });
	const texte = formulaire.locator('[contenteditable="true"]');
	//  Le curseur est DANS le texte : on écrit sans chercher le champ.
	await expect(texte).toBeFocused();
	await page.keyboard.type('Toujours bloqué ce matin.');
	await formulaire.getByRole('button', { name: 'Enregistrer' }).click();
	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0]).toMatchObject({
		contenu: expect.stringContaining('Toujours bloqué ce matin.'),
	});
	//  Le message rejoint le fil, et le formulaire se referme.
	await expect(page.locator('#msg-90')).toContainText('Toujours bloqué ce matin.');
	await expect(formulaire).toHaveCount(0);
});

test('sur la page de l’affaire : l’icône ouvre le formulaire sur place', async ({ page }) => {
	await simuler(page);
	await page.goto('/tickets/7');
	await attendreHydratation(page);

	await expect(page.getByRole('group', { name: 'Répondre' })).toHaveCount(0);
	await icone(page, 7, 'Répondre').click();
	await expect(page).toHaveURL(/\/tickets\/7$/);
	const formulaire = page.getByRole('group', { name: 'Répondre' });
	await expect(formulaire.locator('[contenteditable="true"]')).toBeFocused();
	//  UN formulaire : le bouton du bas a laissé sa place.
	await expect(page.locator('.carte-repondre')).toHaveCount(0);
});

test('au téléphone, six icônes laissent sa place au titre', async ({ page }) => {
	await page.setViewportSize({ width: 360, height: 740 });
	await simuler(page);
	await page.goto('/tickets');
	await attendreHydratation(page);

	const carte = page.locator('#ticket-7');
	await expect(icone(page, 7, 'Répondre')).toBeVisible();
	await expect(carte.locator('.ec-droite--titre button')).toHaveCount(6);
	await attendreSansDefilementHorizontal(page);
	const titre = await carte.getByRole('button', { name: /Ascenseur en panne/ }).boundingBox();
	expect(titre?.width ?? 0).toBeGreaterThanOrEqual(160);
	await page.screenshot({ path: 'test-results/repondre-depuis-la-carte-360.png' });
});
