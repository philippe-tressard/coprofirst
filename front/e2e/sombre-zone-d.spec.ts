/*
 *  **Mode sombre, zone d : les aperçus restent clairs, le logo reste lisible**
 *  (#2174, lot S4d, 29/10/2026).
 *
 *  ## Ce que le parcours de la zone a trouvé, sous `data-theme="dark"`
 *
 *  - le corps d'un modèle de courriel (Admin › Modèles e-mail, « Aperçu »)
 *    s'affichait en texte clair sur bleu nuit : l'aperçu montrait un courriel
 *    qui ne partira jamais ainsi ;
 *  - l'affiche du hall et le courriel de la Diffusion, rendus dans un `<iframe>`,
 *    paraissaient blancs PAR ACCIDENT — le navigateur peint un canevas opaque
 *    quand le schéma du cadre et celui du document embarqué diffèrent ;
 *  - un logo téléversé à l'encre foncée disparaissait sur la carte sombre.
 *
 *  Éditeur riche, contenu saisi, pages de connexion et légales suivaient déjà
 *  les jetons : rien à y corriger (captures du lot).
 *
 *  ## Ce que ce spec tient
 *
 *  Chaque aperçu est un îlot clair (`styles/ilots-clairs.css`) : schéma `light`,
 *  fond blanc, texte du thème clair — au sombre forcé, et à l'identique au
 *  clair. `lint:ilots-clairs` exige la classe dans la source ; ce spec mesure ce
 *  que le navigateur en fait. Le logo : son fond est invisible au clair, blanc
 *  au sombre.
 */
import type { Page } from '@playwright/test';
import type { ApercuDiffusion } from '#lib/api/index.ts';
import type { ModeleEmail } from '#lib/api/types-administration.ts';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const BLANC = 'rgb(255, 255, 255)';
const TEXTE_CLAIR = 'rgb(26, 26, 46)'; // --color-text du thème clair, #1a1a2e
const TRANSPARENT = 'rgba(0, 0, 0, 0)';

async function theme(page: Page, sombre: boolean) {
	await page.evaluate((s) => {
		if (s) document.documentElement.setAttribute('data-theme', 'dark');
		else document.documentElement.removeAttribute('data-theme');
	}, sombre);
}

/** Le schéma, le fond et le texte d'un élément. */
function rendu(page: Page, selecteur: string) {
	return page
		.locator(selecteur)
		.first()
		.evaluate((el) => {
			const s = getComputedStyle(el);
			return { schema: s.colorScheme, fond: s.backgroundColor, texte: s.color };
		});
}

/** L'îlot rend le même aperçu clair dans les deux thèmes — et le sombre est bien allumé autour. */
async function attendreIlotClair(page: Page, selecteur: string, texte = false) {
	for (const sombre of [false, true]) {
		await theme(page, sombre);
		const r = await rendu(page, selecteur);
		expect(r.schema, `${selecteur} : schéma (${sombre ? 'sombre' : 'clair'})`).toBe('light');
		expect(r.fond, `${selecteur} : fond (${sombre ? 'sombre' : 'clair'})`).toBe(BLANC);
		if (texte) expect(r.texte, `${selecteur} : texte`).toBe(TEXTE_CLAIR);
	}
	//  Cas zéro : sans le sombre allumé autour de l'îlot, la mesure ne prouverait rien.
	const page_ = await page.evaluate(() => getComputedStyle(document.body).color);
	expect(page_, 'le thème sombre n’est pas allumé autour de l’aperçu').not.toBe(TEXTE_CLAIR);
}

const COURRIEL = '<table><tr><td>Bonjour, une affaire a été ouverte.</td></tr></table>';
const APERCU: ApercuDiffusion = {
	canaux: [
		{
			canal: 'email',
			actif: true,
			destinataires: ['durand@exemple.test'],
			ecartes: [],
			sujet: 'Affaire — Fuite',
			corps_html: COURRIEL,
			ampute: false,
			avec_photo: false,
		},
	],
	attribues_a_la_creation: [],
};

test('@sombre l’aperçu du courriel de la Diffusion est un îlot clair', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets/apercu-diffusion') return APERCU;
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();
	await page
		.getByText(/Ascenseur, chauffage, éclairage/)
		.first()
		.click();
	await page.getByLabel(/Titre/).first().fill('Fuite au sous-sol');
	await page
		.getByLabel(/Description/)
		.first()
		.fill('Une fuite.');
	await page
		.getByRole('button', { name: /^Créer|^Enregistrer|^Signaler/ })
		.first()
		.click();
	await expect(page.locator('.apercu-corps-cadre')).toBeVisible();
	await attendreIlotClair(page, '.apercu-corps-cadre');
});

const MODELE: ModeleEmail = {
	id: 1,
	code: 'affaire_creee',
	libelle: 'Affaire créée',
	sujet: 'Affaire',
	corps_html: '<p>Bonjour,</p><blockquote><p>Une affaire a été ouverte.</p></blockquote>',
	variables_disponibles: '[]',
	intention: '',
	desactivable: true,
	actif: true,
	modifie_par_id: null,
	modifie_le: null,
};

test('@sombre l’aperçu d’un modèle de courriel est un îlot clair, texte compris', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
		if (chemin === '/api/admin/modeles-email') return [MODELE];
	});
	await page.goto('/admin?onglet=emails');
	await attendreHydratation(page);
	await page
		.getByRole('button', { name: /Modifier/ })
		.first()
		.click();
	await page
		.getByRole('button', { name: /Aperçu/ })
		.first()
		.click();
	await expect(page.locator('.apercu-email')).toContainText('Une affaire a été ouverte.');
	await attendreIlotClair(page, '.apercu-email', true);
	//  Le texte injecté hérite de l'îlot, pas de la page sombre.
	await theme(page, true);
	expect(await rendu(page, '.apercu-email blockquote')).toMatchObject({ schema: 'light' });
});

test('@sombre l’aperçu de l’affiche du hall est un îlot clair', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/annonces-hall/previsualiser')
			return { html: '<p>Coupure d’eau</p>', format_label: 'A4' };
	});
	await page.goto('/espace-cs/annonces-hall');
	await attendreHydratation(page);
	await page.locator('#ah-titre').fill('Coupure d’eau');
	await page.locator('.rich-content-editable .tiptap').first().click();
	await page.keyboard.type('Mardi de 9 h à 12 h.');
	await page
		.getByRole('button', { name: /^Aperçu/ })
		.first()
		.click();
	await expect(page.locator('.ah-apercu-frame')).toBeVisible();
	await attendreIlotClair(page, '.ah-apercu-cadre');
	expect((await rendu(page, '.ah-apercu-frame')).schema, 'le cadre hérite du schéma').toBe('light');
});

test('@sombre le logo téléversé garde son fond clair au sombre, et rien au clair', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return undefined;
		if (chemin.startsWith('/api/config')) return { site_logo: 'v1' };
	});
	//  Après `simulerApi` : Playwright essaie la route la plus récente d'abord.
	await page.route(
		(url) => url.pathname.startsWith('/api/config/logo'),
		(route) =>
			route.fulfill({
				contentType: 'image/svg+xml',
				body: '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96"><rect width="40" height="40"/></svg>',
			}),
	);
	await page.goto('/auth/connexion');
	const logo = page.locator('.logo-residence');
	await expect(logo).toBeVisible();
	const fond = () =>
		logo.evaluate((el) => {
			const s = getComputedStyle(el);
			return { fond: s.backgroundColor, liseré: s.boxShadow };
		});
	await theme(page, false);
	const clair = await fond();
	expect(clair.fond).toBe(TRANSPARENT);
	expect(clair.liseré).toContain(TRANSPARENT);
	await theme(page, true);
	const sombre = await fond();
	expect(sombre.fond).toBe(BLANC);
	expect(sombre.liseré).toContain(BLANC);
});
