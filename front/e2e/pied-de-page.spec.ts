/*
 *  **Le pied de page se règle dans Admin › Site, sauf quatre éléments (08/10/2026).**
 *
 *  Demandé : « rends la signature éditable sur la base des éléments
 *  actuellement disponibles », et la version ramenée à « v2.118.1 · RPi1 »,
 *  sans l'empreinte ni la date du build. Ce test rend le VRAI écran, avec l'API
 *  simulée, et vérifie ce qu'on LIT : un élément masqué disparaît, les éléments
 *  verrouillés (la marque, le code source, les mentions légales, la
 *  confidentialité) restent même quand la configuration en base demande de les
 *  masquer, et l'aperçu de l'administration suit la pastille avant tout
 *  enregistrement.
 *
 *  Depuis le 15/10/2026, une CARTE (maquette A) : la marque — logo et nom en
 *  gras — à gauche, les mentions sous le nom, les liens à droite. L'ordre réglé
 *  vaut dans chaque place.
 *
 *  Depuis le 17/10/2026 (#2040), DEUX liens vers le logiciel, nommés pour des
 *  novices : « À propos de CoproFirst » (le site de présentation, masquable)
 *  et « Logiciel libre » (le code source, verrouillé par l'AGPL). Tous deux
 *  sortent du site : nouvel onglet, icône de sortie décorative, infobulle.
 *  Au téléphone, la carte passe à trois lignes centrées.
 */
import type { Page } from '@playwright/test';
import { DEPOT_SOURCE, NOM_PLATEFORME, SITE_PLATEFORME } from '../src/lib/plateforme';
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
//  La version seule — ni empreinte ni date de build accolées.
const VERSION = /^v\d+\.\d+\.\d+$/;
const A_PROPOS = `À propos de ${NOM_PLATEFORME}`;
const SOURCE = 'Logiciel libre';

async function piedSansReglage(page: Page) {
	await simulerApi(page, (chemin) =>
		chemin === '/api/config' ? { site_nom: '5Hostachy' } : undefined,
	);
	await page.goto('/tableau-de-bord');
	return page.locator('footer.app-footer');
}

test('sans réglage, la carte montre la marque, les mentions et les liens', async ({ page }) => {
	const pied = await piedSansReglage(page);
	const nom = pied.locator('.nom');
	await expect(nom).toHaveText('5Hostachy');
	//  « en gras » : la partie non négociable de la maquette.
	await expect(nom).toHaveCSS('font-weight', '700');
	await expect(pied.locator('.mentions')).toContainText(`© ${new Date().getFullYear()}`);
	await expect(pied.locator('.mentions').getByText(VERSION)).toBeVisible();
	const liens = pied.getByRole('navigation', { name: 'Pied de page' });
	await expect(liens.getByRole('link')).toHaveText([
		A_PROPOS,
		SOURCE,
		'Mentions légales',
		'Confidentialité',
	]);
});

test('les deux liens du logiciel sortent du site : nouvel onglet, icône, infobulle', async ({
	page,
}) => {
	const liens = (await piedSansReglage(page)).getByRole('navigation', { name: 'Pied de page' });
	const attendus = [
		{
			nom: A_PROPOS,
			cible: SITE_PLATEFORME,
			infobulle: `Le site de présentation de ${NOM_PLATEFORME}, le logiciel qui fait tourner ce site`,
		},
		//  « Logiciel libre » ne dit pas « code » : l'infobulle porte l'offre (AGPLv3 §13).
		{ nom: SOURCE, cible: DEPOT_SOURCE, infobulle: 'Le code source de la version en service' },
	];
	for (const { nom, cible, infobulle } of attendus) {
		const lien = liens.getByRole('link', { name: nom, exact: true });
		await expect(lien).toHaveAttribute('href', new RegExp(`^${cible}`));
		await expect(lien).toHaveAttribute('target', '_blank');
		await expect(lien).toHaveAttribute('rel', /\bnoopener\b/);
		await expect(lien).toHaveAttribute('title', infobulle);
		await expect(lien.locator('svg[aria-hidden="true"]')).toHaveCount(1);
	}
	//  Les liens internes restent dans le site, sans icône de sortie.
	for (const nom of ['Mentions légales', 'Confidentialité']) {
		const lien = liens.getByRole('link', { name: nom, exact: true });
		await expect(lien).not.toHaveAttribute('target');
		await expect(lien.locator('svg')).toHaveCount(0);
	}
});

test('au téléphone, trois lignes centrées ; au bureau, les mentions à côté du logo', async ({
	page,
}) => {
	const pied = await piedSansReglage(page);
	const carte = pied.locator('.carte-pied');
	await expect(pied.locator('.nom')).toHaveText('5Hostachy');
	/** Pour chaque ligne de la carte, l'écart (px) entre son centre et celui de la carte. */
	const ecarts = () =>
		carte.evaluate((el) => {
			const boite = el.getBoundingClientRect();
			const milieu = boite.left + boite.width / 2;
			const lignes = new Map<number, { g: number; d: number }>();
			const selecteur =
				'.marque-pied > :first-child, .nom, .mentions > .element, .liens > .element';
			el.querySelectorAll(selecteur).forEach((n) => {
				const b = n.getBoundingClientRect();
				//  Une ligne : les éléments de même centre vertical (le logo est plus haut que le nom).
				const cle = Math.round((b.top + b.bottom) / 20);
				const l = lignes.get(cle) ?? { g: Infinity, d: -Infinity };
				lignes.set(cle, { g: Math.min(l.g, b.left), d: Math.max(l.d, b.right) });
			});
			return [...lignes.values()].map((l) => Math.round(Math.abs((l.g + l.d) / 2 - milieu)));
		});
	const hauts = () =>
		carte.evaluate((el) =>
			['.nom', '.mentions', '.liens'].map((s) => el.querySelector(s)!.getBoundingClientRect().top),
		);

	await page.setViewportSize({ width: 360, height: 800 });
	//  Trois lignes au moins (les liens peuvent en prendre deux), chacune centrée.
	await expect.poll(async () => (await ecarts()).length).toBeGreaterThanOrEqual(3);
	await expect.poll(async () => Math.max(...(await ecarts()))).toBeLessThanOrEqual(2);
	await expect
		.poll(async () => {
			const [nom, mentions, liens] = await hauts();
			return nom < mentions && mentions < liens;
		})
		.toBe(true);

	//  Le bureau ne change pas : les mentions restent sous le nom, à côté du logo.
	await page.setViewportSize({ width: 1280, height: 800 });
	await expect
		.poll(() =>
			carte.evaluate((el) => {
				const logo = el.querySelector('.marque-pied > :first-child')!.getBoundingClientRect();
				return el.querySelector('.mentions')!.getBoundingClientRect().left >= logo.right;
			}),
		)
		.toBe(true);
});

test('un élément masqué disparaît ; un élément verrouillé reste', async ({ page }) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/config'
			? {
					site_nom: '5Hostachy',
					pied_de_page_masques: 'annee,version,residence,site,source,mentions,confidentialite',
				}
			: undefined,
	);
	await page.goto('/tableau-de-bord');
	const pied = page.locator('footer.app-footer');
	//  Cas zéro : le pied de page est bien rendu avant qu'on y cherche une absence.
	await expect(pied.locator('.nom')).toHaveText('5Hostachy');
	await expect(pied).toContainText('Mentions légales');
	await expect(pied).toContainText('Confidentialité');
	await expect(pied).toContainText(SOURCE);
	//  Le site de présentation se masque : aucune obligation ne l'impose.
	await expect(pied).not.toContainText(A_PROPOS);
	await expect(pied).not.toContainText('©');
	await expect(pied).not.toContainText(/v\d+\.\d+\.\d+/);
});

test('Admin › Connexion et pied de page : la marque est fixe, la pastille masque l’élément dans l’aperçu', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await page.goto('/admin?onglet=connexion');
	const mentions = page.getByRole('group', { name: 'Sous le nom' });
	const liens = page.getByRole('group', { name: 'Liens, à droite' });
	const apercu = page.getByRole('group', { name: 'Aperçu du pied de page' });
	const annee = mentions.getByRole('button', { name: '© Année', exact: true });

	await expect(page.getByText('Logo et nom de la résidence')).toBeVisible();
	await expect(page.getByRole('button', { name: /« Logo et nom de la résidence »/ })).toHaveCount(
		0,
	);
	await expect(annee).toHaveAttribute('aria-pressed', 'true');
	await expect(apercu).toContainText('©');
	//  Un élément verrouillé ne se masque pas — il n'a pas de pastille — mais il se déplace.
	await expect(liens.getByRole('button', { name: 'Mentions légales', exact: true })).toHaveCount(0);
	await expect(liens.getByRole('button', { name: 'Monter « Mentions légales »' })).toBeEnabled();

	await annee.click();
	await expect(annee).toHaveAttribute('aria-pressed', 'false');
	await expect(apercu).not.toContainText('©');
	await expect(apercu).toContainText('Mentions légales');
});

test('l’ordre réglé vaut dans chaque place, le préfixe et l’année se lisent', async ({ page }) => {
	const courante = new Date().getFullYear();
	await simulerApi(page, (chemin) =>
		chemin === '/api/config'
			? {
					site_nom: '5Hostachy',
					pied_de_page_annee_debut: String(courante - 1),
					//  Un ordre enregistré avant la carte, qui mêle les places : chacune
					//  y garde son ordre relatif, sans migration.
					pied_de_page_ordre: 'version,confidentialite,residence,annee,source',
					pied_de_page_prefixe_nom: 'Résidence',
				}
			: undefined,
	);
	await page.goto('/tableau-de-bord');
	const pied = page.locator('footer.app-footer');
	await expect(pied.locator('.nom')).toHaveText(/^Résidence\s5Hostachy$/);
	await expect(pied.locator('.mentions > .element')).toHaveText([
		VERSION,
		`© ${courante - 1}–${courante}`,
	]);
	//  Les éléments absents de l'ordre réglé viennent ensuite : rien ne disparaît.
	await expect(pied.locator('.liens > .element')).toHaveText([
		'Confidentialité',
		SOURCE,
		A_PROPOS,
		'Mentions légales',
	]);
});

test('Admin › Connexion et pied de page : un lien monte et descend dans sa place, l’aperçu suit', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await page.goto('/admin?onglet=connexion');
	const liens = page.getByRole('group', { name: 'Liens, à droite' });
	const apercu = page.getByRole('group', { name: 'Aperçu du pied de page' });
	const elements = apercu.locator('.liens > .element');
	const rang = async () => (await elements.allTextContents()).findIndex((t) => t.trim() === SOURCE);
	//  L'aperçu se rend après le chargement de la configuration : attendre qu'il y soit.
	await expect.poll(rang, { message: `${SOURCE} doit paraître dans l’aperçu` }).toBe(1);
	//  Le site de présentation se masque, lui : il a sa pastille.
	await expect(liens.getByRole('button', { name: A_PROPOS, exact: true })).toHaveAttribute(
		'aria-pressed',
		'true',
	);
	const monter = liens.getByRole('button', { name: `Monter « ${SOURCE} »` });
	await monter.click();
	await expect.poll(rang).toBe(0);
	await expect(monter).toBeDisabled();
	//  Un élément VERROUILLÉ se déplace aussi : le lien du code descend jusqu'au bout.
	const descendre = liens.getByRole('button', { name: `Descendre « ${SOURCE} »` });
	while (await descendre.isEnabled()) await descendre.click();
	await expect.poll(rang).toBe(3);
	await monter.click();
	await expect.poll(rang).toBe(2);
	//  Pas de texte d'exemple qui se lise comme une valeur saisie (09/10/2026).
	for (const champ of ['Année de création', 'Texte avant le nom']) {
		await expect(page.getByLabel(champ)).not.toHaveAttribute('placeholder');
	}
	await page.getByLabel('Texte libre', { exact: true }).fill('Texte du conseil');
	await expect(apercu.locator('.mentions')).toContainText('Texte du conseil');
});
