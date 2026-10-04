/*
 *  **Un seul éditeur riche, deux barres** (#1539, 02/10/2026).
 *
 *  `LegalEditor` (mentions légales, confidentialité) recopiait l'amorçage de
 *  `RichEditor` ; il y est fondu, et ce qui le distinguait est DÉCLARÉ en props
 *  (`titres`, `sourceHtml`). Ce test tient ce que la fusion ne devait pas
 *  perdre, sur le VRAI écran, API simulée :
 *
 *  - l'éditeur légal garde ses titres, son filet et son mode « source HTML » ;
 *  - un texte corrigé dans la source revient dans l'éditeur visuel, et c'est
 *    lui qui part à l'enregistrement ;
 *  - un éditeur de description, lui, n'a ni titres ni source.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
const LEGAL = {
	mentions_legales: '<h2>Éditeur</h2><p>Le syndicat des copropriétaires.</p>',
	politique_confidentialite: '<p>Vos données restent ici.</p>',
};

type Envoi = { quoi: string; corps: unknown };

async function ouvrir(page: Page, chemin: string): Promise<Envoi[]> {
	const envois: Envoi[] = [];
	page.on('request', (r) => {
		const url = new URL(r.url());
		if (url.pathname.startsWith('/api/') && r.method() !== 'GET')
			envois.push({ quoi: `${r.method()} ${url.pathname}`, corps: r.postDataJSON() });
	});
	await simulerApi(page, (api) => {
		if (api === '/api/auth/me') return ADMIN;
		if (api === '/api/config/legal') return LEGAL;
	});
	await page.goto(chemin);
	await attendreHydratation(page);
	return envois;
}

test('l’éditeur légal garde ses titres, son filet et sa source HTML', async ({ page }) => {
	const envois = await ouvrir(page, '/admin?onglet=legal');
	const editeur = page.locator('.editeur-cadre').first();
	await expect(editeur.locator('.tiptap h2')).toHaveText('Éditeur');
	for (const nom of ['Titre H2', 'Titre H3', 'Ligne de séparation', 'Gras', 'Annuler']) {
		await expect(editeur.getByRole('button', { name: nom, exact: true })).toBeVisible();
	}

	await editeur.getByRole('button', { name: 'Source HTML' }).click();
	const source = editeur.getByRole('textbox', { name: 'Source HTML' });
	await expect(source).toHaveValue(LEGAL.mentions_legales);
	//  En mode source, la barre de mise en forme se retire.
	await expect(editeur.getByRole('button', { name: 'Gras', exact: true })).toHaveCount(0);
	await source.fill('<h2>Hébergeur</h2><p>Chez nous.</p>');

	await editeur.getByRole('button', { name: 'Mode éditeur' }).click();
	await expect(source).toHaveCount(0);
	await expect(editeur.locator('.tiptap h2')).toHaveText('Hébergeur');

	await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	await expect
		.poll(() => envois.some((e) => JSON.stringify(e.corps ?? '').includes('<h2>Hébergeur</h2>')))
		.toBe(true);
});

test('un éditeur de description n’a ni titres ni source', async ({ page, baseURL }) => {
	//  `/prestataires` a une garde SERVEUR qui ne regarde que la PRÉSENCE du cookie.
	await page.context().addCookies([{ name: 'access_token', value: 'temoin', url: baseURL }]);
	await ouvrir(page, '/prestataires');
	await page.getByRole('button', { name: 'Nouveau prestataire' }).click();
	//  Section facultative, donc pliée : on la déplie.
	await page.getByRole('button', { name: /^Description/ }).click();
	const editeur = page.locator('.editeur-cadre').first();
	await expect(editeur.getByRole('button', { name: 'Gras', exact: true })).toBeVisible();
	await expect(editeur.getByRole('button', { name: 'Titre H2' })).toHaveCount(0);
	await expect(editeur.getByRole('button', { name: 'Source HTML' })).toHaveCount(0);
});

test('l’éditeur ne se télécharge qu’à l’ouverture d’un formulaire', async ({ page, baseURL }) => {
	//  Tiptap et ProseMirror pesaient 121 Ko compressés dans le chargement
	//  initial de chaque écran qui CONTIENT un formulaire, même replié (04/10/2026) :
	//  `RichEditor` les charge désormais par `import()`. Le build est tenu par
	//  `lint:poids-ouverture` ; ce test tient le COMPORTEMENT — rien à
	//  l'ouverture, un éditeur qui marche une fois le formulaire déplié.
	const tiptap: string[] = [];
	page.on('request', (r) => {
		if (/tiptap|prosemirror/i.test(r.url())) tiptap.push(r.url());
	});
	await page.context().addCookies([{ name: 'access_token', value: 'temoin', url: baseURL }]);
	await ouvrir(page, '/prestataires');
	await expect(page.getByRole('button', { name: 'Nouveau prestataire' })).toBeVisible();
	expect(tiptap, 'Tiptap téléchargé à l’ouverture de l’écran').toEqual([]);

	await page.getByRole('button', { name: 'Nouveau prestataire' }).click();
	await page.getByRole('button', { name: /^Description/ }).click();
	const zone = page.locator('.editeur-cadre .tiptap').first();
	await expect(zone).toBeVisible();
	expect(tiptap.length).toBeGreaterThan(0);
	await zone.click();
	await page.keyboard.type('Entreprise de plomberie');
	await expect(zone).toContainText('Entreprise de plomberie');
});
