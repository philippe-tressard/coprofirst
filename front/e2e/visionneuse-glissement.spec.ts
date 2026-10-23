/*
 *  **Le glissement de la visionneuse** (#2169, audit `apple-design` du 23/10/2026).
 *
 *  Le geste ne lisait que son départ et son arrivée : la photo ne suivait pas
 *  le doigt, changeait d'un coup au lâcher, et un geste vif mais court ne
 *  comptait pas — le seuil était une distance. Ce test tient les trois :
 *
 *  1. pendant le glissement, la photo est DÉPLACÉE (elle suit le pointeur) ;
 *  2. un geste vif et court change de photo ;
 *  3. un geste lent et court la remet à sa place.
 *
 *  Le pointeur de la souris émet les mêmes `pointer*` que le doigt : c'est le
 *  même jeu d'écouteurs (`Lightbox.svelte`).
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const AFFAIRE = {
	id: 7,
	numero: 'TK-124301',
	titre: 'Porte du local vélos',
	description: 'La gâche ne tient plus.',
	categorie: 'panne',
	statut: 'ouvert',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	photos_urls: ['/uploads/gache-1.png', '/uploads/gache-2.png'],
	fichiers_urls: [],
	archivee: false,
	natures: ['activite'],
	cree_le: '2026-09-20T10:00:00',
	mis_a_jour_le: '2026-09-20T10:00:00',
};

//  Une image de 2 × 2 pixels : la visionneuse a besoin d'une photo qui se charge.
const PNG = Buffer.from(
	'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8z8DAwMDAxMDAwMDAAAANHQEDasKb6QAAAABJRU5ErkJggg==',
	'base64',
);

async function ouvrirLaPhoto(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [AFFAIRE];
		if (chemin === '/api/tickets/7') return AFFAIRE;
		if (chemin === '/api/tickets/7/evolutions') return [];
	});
	await page.route('**/uploads/**', (r) =>
		r.fulfill({ status: 200, contentType: 'image/png', body: PNG }),
	);
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.locator('.carte-liste').first().getByText(AFFAIRE.titre).click();
	await page.getByRole('button', { name: 'Agrandir gache-1.png' }).click();
	await expect(page.locator('.lb-compteur')).toHaveText('1 / 2');
}

/** Le centre de l'écran : la photo, petite, ne couvre pas toujours la largeur du geste. */
async function centre(page: Page): Promise<[number, number]> {
	const t = page.viewportSize() ?? { width: 800, height: 600 };
	return [t.width / 2, t.height / 2];
}

test('pendant le glissement, la photo suit le pointeur ; au-delà du seuil, elle change', async ({
	page,
}) => {
	await ouvrirLaPhoto(page);
	const [x, y] = await centre(page);
	await page.mouse.move(x, y);
	await page.mouse.down();
	await page.mouse.move(x - 80, y, { steps: 8 });
	await expect
		.poll(() => page.locator('.lb-image').evaluate((e) => (e as HTMLElement).style.transform))
		.toContain('translateX(-');
	await page.mouse.up();
	await expect(page.locator('.lb-compteur')).toHaveText('2 / 2');
	//  Le glissement n'a pas refermé la visionneuse (le `click` de fin de geste).
	await expect(page.getByRole('dialog', { name: 'Photo en plein écran' })).toBeVisible();
});

test('un geste vif et court change de photo', async ({ page }) => {
	await ouvrirLaPhoto(page);
	const [x, y] = await centre(page);
	await page.mouse.move(x, y);
	await page.mouse.down();
	await page.mouse.move(x - 30, y, { steps: 2 });
	await page.mouse.up();
	await expect(page.locator('.lb-compteur')).toHaveText('2 / 2');
});

test('un geste lent et court remet la photo à sa place', async ({ page }) => {
	await ouvrirLaPhoto(page);
	const [x, y] = await centre(page);
	await page.mouse.move(x, y);
	await page.mouse.down();
	await page.mouse.move(x - 30, y, { steps: 3 });
	//  Le doigt s'arrête avant de lâcher : la vitesse au lâcher est nulle.
	await page.waitForTimeout(300);
	await page.mouse.up();
	await expect
		.poll(() => page.locator('.lb-image').evaluate((e) => (e as HTMLElement).style.transform))
		.toBe('');
	await expect(page.locator('.lb-compteur')).toHaveText('1 / 2');
});
