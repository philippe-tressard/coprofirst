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
 */
import { NOM_PLATEFORME } from '../src/lib/plateforme';
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
//  La version seule — ni empreinte ni date de build accolées.
const VERSION = /^v\d+\.\d+\.\d+$/;

test('sans réglage, la carte montre la marque, les mentions et les liens', async ({ page }) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/config' ? { site_nom: '5Hostachy' } : undefined,
	);
	await page.goto('/tableau-de-bord');
	const pied = page.locator('footer.app-footer');
	const nom = pied.locator('.nom');
	await expect(nom).toHaveText('5Hostachy');
	//  « en gras » : la partie non négociable de la maquette.
	await expect(nom).toHaveCSS('font-weight', '700');
	await expect(pied.locator('.mentions')).toContainText(`© ${new Date().getFullYear()}`);
	await expect(pied.locator('.mentions').getByText(VERSION)).toBeVisible();
	const liens = pied.getByRole('navigation', { name: 'Pied de page' });
	await expect(liens.getByRole('link')).toHaveText([
		`${NOM_PLATEFORME} (code source)`,
		'Mentions légales',
		'Confidentialité',
	]);
});

test('un élément masqué disparaît ; un élément verrouillé reste', async ({ page }) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/config'
			? {
					site_nom: '5Hostachy',
					pied_de_page_masques: 'annee,version,residence,source,mentions,confidentialite',
				}
			: undefined,
	);
	await page.goto('/tableau-de-bord');
	const pied = page.locator('footer.app-footer');
	//  Cas zéro : le pied de page est bien rendu avant qu'on y cherche une absence.
	await expect(pied.locator('.nom')).toHaveText('5Hostachy');
	await expect(pied).toContainText('Mentions légales');
	await expect(pied).toContainText('Confidentialité');
	await expect(pied).toContainText(NOM_PLATEFORME);
	await expect(pied).not.toContainText('©');
	await expect(pied).not.toContainText(/v\d+\.\d+\.\d+/);
});

test('Admin › Site : la marque est fixe, la pastille masque l’élément dans l’aperçu', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await page.goto('/admin?onglet=site');
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
		`${NOM_PLATEFORME} (code source)`,
		'Mentions légales',
	]);
});

test('Admin › Site : un lien monte et descend dans sa place, l’aperçu suit', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await page.goto('/admin?onglet=site');
	const liens = page.getByRole('group', { name: 'Liens, à droite' });
	const apercu = page.getByRole('group', { name: 'Aperçu du pied de page' });
	const elements = apercu.locator('.liens > .element');
	const rang = async () =>
		(await elements.allTextContents()).findIndex((t) => t.startsWith(NOM_PLATEFORME));
	//  L'aperçu se rend après le chargement de la configuration : attendre qu'il y soit.
	await expect.poll(rang, { message: `${NOM_PLATEFORME} doit paraître dans l’aperçu` }).toBe(0);
	const libelle = `${NOM_PLATEFORME} (code source)`;
	await expect(liens.getByRole('button', { name: `Monter « ${libelle} »` })).toBeDisabled();
	//  Un élément VERROUILLÉ se déplace aussi : le lien du logiciel descend jusqu'au bout.
	const descendre = liens.getByRole('button', { name: `Descendre « ${libelle} »` });
	while (await descendre.isEnabled()) await descendre.click();
	await expect.poll(rang).toBe(2);
	await liens.getByRole('button', { name: `Monter « ${libelle} »` }).click();
	await expect.poll(rang).toBe(1);
	//  Pas de texte d'exemple qui se lise comme une valeur saisie (09/10/2026).
	for (const champ of ['Année de création', 'Texte avant le nom']) {
		await expect(page.getByLabel(champ)).not.toHaveAttribute('placeholder');
	}
	await page.getByLabel('Texte libre', { exact: true }).fill('Texte du conseil');
	await expect(apercu.locator('.mentions')).toContainText('Texte du conseil');
});
