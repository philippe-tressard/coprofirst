/*
 *  **L'identité de la copropriété : une saisie, deux écrans** (#779, 01/10/2026).
 *
 *  Admin › Fiche copropriété et la fiche de la page Résidence saisissaient nom,
 *  adresse, décomptes de lots, année et immatriculation chacune à sa façon. La
 *  copie de Résidence n'ENVOYAIT pas un nombre vidé : l'ancienne valeur restait,
 *  sans un mot. Les deux passent par `ChampsIdentiteCopropriete` ; ce test tient,
 *  sur la requête réellement envoyée, ce que la factorisation devait corriger
 *  — un nombre vidé part à `null`, des deux écrans.
 *
 *  Et sa DISPOSITION (02/10/2026, maquette B) : posés nus dans la grille de
 *  l'écran, les champs prenaient chacun 220 px — adresse tronquée, et les deux
 *  libellés ANAH sur deux lignes, saisies décalées. Le dernier test mesure ce
 *  que l'œil avait vu : les quatre saisies de la rangée des lots alignées,
 *  l'adresse deux fois plus large que le nom.
 */
import type { Page, Request } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
const FICHE = {
	id: 1,
	nom: 'Résidence témoin',
	adresse: '1 rue Exemple',
	nb_lots_total: 195,
	nb_lots_principaux: 63,
	annee_construction: 1975,
	numero_immatriculation: 'AA0000000',
};

async function ouvrir(page: Page, adresse: string, compte = MEMBRE_CS): Promise<Request[]> {
	const envois: Request[] = [];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return compte;
		if (chemin === '/api/copropriete') return FICHE;
	});
	page.on('request', (r) => {
		if (r.method() === 'PATCH' && new URL(r.url()).pathname === '/api/copropriete') envois.push(r);
	});
	await page.goto(adresse);
	await attendreHydratation(page);
	return envois;
}

async function viderLesLots(page: Page) {
	await expect(page.getByLabel(/Nom de la résidence/)).toHaveValue(FICHE.nom);
	await page.getByLabel(/^Total/).fill('');
	await page.getByRole('button', { name: /Enregistrer/ }).click();
}

test('Résidence : un nombre vidé part à null — il s’efface', async ({ page }) => {
	//  L'administrateur seul modifie la fiche : `PATCH /copropriete` l'exige (#2096).
	const envois = await ouvrir(page, '/residence', ADMIN);
	await page.getByRole('button', { name: 'Modifier la fiche de la résidence' }).click();
	await viderLesLots(page);
	await expect.poll(() => envois.length).toBe(1);
	const corps = envois[0].postDataJSON();
	expect(corps.nb_lots_total).toBeNull();
	expect(corps.nom).toBe(FICHE.nom);
	expect(corps.nb_lots_principaux).toBe(63);
});

test('Résidence : le conseil syndical lit la fiche, sans crayon qui finirait en 403 (#2096)', async ({
	page,
}) => {
	await ouvrir(page, '/residence');
	await expect(page.getByRole('heading', { name: `Résidence : ${FICHE.nom}` })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Modifier la fiche de la résidence' })).toHaveCount(
		0,
	);
});

test('Admin › Fiche : les mêmes champs, la même règle', async ({ page }) => {
	const envois = await ouvrir(page, '/admin?onglet=copropriete', ADMIN);
	await viderLesLots(page);
	await expect.poll(() => envois.length).toBe(1);
	const corps = envois[0].postDataJSON();
	expect(corps.nb_lots_total).toBeNull();
	expect(corps.annee_construction).toBe(1975);
});

test('Admin › Fiche : adresse large, saisies de la rangée des lots alignées', async ({
	page,
}, info) => {
	await ouvrir(page, '/admin?onglet=copropriete', ADMIN);
	const boite = async (libelle: RegExp) => (await page.getByLabel(libelle).boundingBox())!;
	const nom = await boite(/Nom de la résidence/);
	const adresse = await boite(/^Adresse/);
	const saisies = [
		await boite(/^Total/),
		await boite(/^Dont lots principaux/),
		await boite(/^Année de construction/),
		await boite(/^N° immatriculation/),
	];
	if (info.project.name.includes('mobile')) {
		//  Une colonne : chaque saisie sous la précédente, aucune côte à côte.
		expect(adresse.y).toBeGreaterThan(nom.y);
		return;
	}
	expect(adresse.width).toBeGreaterThan(nom.width * 1.8);
	for (const s of saisies.slice(1)) expect(Math.abs(s.y - saisies[0].y)).toBeLessThan(1);
});
