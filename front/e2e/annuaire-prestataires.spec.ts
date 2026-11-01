/*
 *  **La barre de l'annuaire des prestataires** : le filtre de contrat, la
 *  recherche libre, et sa disposition en DEUX lignes sur ordinateur.
 *
 *  ## « Sous contrat » se LIT sur les contrats, il ne se saisit pas (#1444).**
 *
 *  « 🔄 Contrat récurrent » et « Dépannage » étaient des CATÉGORIES de
 *  prestataire. Elles disaient le cadre d'une intervention, pas le métier de
 *  l'entreprise : Otis entretient l'ascenseur sous contrat et le dépanne hors
 *  contrat. Elles sont fondues en « Maintenance & dépannage », et le cadre se
 *  déduit des contrats actifs de la fiche — une pastille sur la carte, un
 *  filtre au-dessus de la liste.
 *
 *  Ce que le test tient, et qu'aucun test unitaire ne verrait : la pastille
 *  suit les CONTRATS servis (et non un champ de la fiche), et le filtre trie
 *  les cartes réellement rendues.
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal } from './defilement';

const OTIS = {
	id: 1,
	nom: 'Otis',
	specialite: 'ascenseur',
	type_prestataire: 'maintenance_depannage',
	actif: true,
};
const PLOMBIER = {
	id: 2,
	nom: 'Plomberie Martin',
	specialite: 'plomberie',
	type_prestataire: 'maintenance_depannage',
	contacts: [{ prenom: 'Hélène', nom: 'Dupré', fonction: 'Gérante' }],
	actif: true,
};
const CONTRAT_OTIS = {
	id: 10,
	prestataire_id: 1,
	copropriete_id: 1,
	type_equipement: 'ascenseur',
	libelle: 'Ascenseur',
	date_debut: '2025-01-01',
	perimetre_cible: ['résidence'],
	actif: true,
};

async function ouvrirAnnuaire(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/prestataires') return [OTIS, PLOMBIER];
		if (chemin === '/api/prestataires/contrats') return [CONTRAT_OTIS];
	});
	await page.goto('/prestataires');
	//  Cas zéro : sans les deux cartes, les assertions suivantes ne prouvent rien.
	await expect(page.locator('#presta-1')).toBeVisible();
	await expect(page.locator('#presta-2')).toBeVisible();
}

test('la carte dit « Sous contrat » d’après ses contrats, et seulement alors', async ({ page }) => {
	await ouvrirAnnuaire(page);
	await expect(page.locator('#presta-1')).toContainText('Sous contrat (1)');
	await expect(page.locator('#presta-2')).not.toContainText('Sous contrat');
	//  La catégorie dit le métier, la même pour les deux.
	await expect(page.locator('#presta-1')).toContainText('Maintenance & dépannage');
	await expect(page.locator('#presta-2')).toContainText('Maintenance & dépannage');
});

test('le filtre sépare les prestataires sous contrat des autres', async ({ page }) => {
	await ouvrirAnnuaire(page);
	const filtre = page.getByRole('group', { name: 'Contrat', exact: true });

	await filtre.getByRole('button', { name: /Sous contrat/ }).click();
	await expect(page.locator('#presta-1')).toBeVisible();
	await expect(page.locator('#presta-2')).toHaveCount(0);

	await filtre.getByRole('button', { name: 'Sans contrat' }).click();
	await expect(page.locator('#presta-2')).toBeVisible();
	await expect(page.locator('#presta-1')).toHaveCount(0);
});

/*
 *  ## La recherche remplace le filtre par équipement (28/09/2026)
 *
 *  Demandé à l'écran : la rangée des douze équipements défilait sous les deux
 *  autres. La recherche doit donc retrouver un prestataire PAR son équipement
 *  — sinon on aurait retiré une capacité — et, comme celle des affaires, sans
 *  accents ni majuscules, tous les mots exigés.
 */
test('la recherche retrouve un prestataire par son équipement, ses contacts, sans accents', async ({
	page,
}) => {
	await ouvrirAnnuaire(page);
	await expect(page.getByRole('group', { name: 'Filtrer par équipement' })).toHaveCount(0);
	const recherche = page.getByRole('searchbox', { name: 'Recherche' });
	//  Le champ tient dans l'écran — au téléphone, il en sortait (422 px pour 363).
	const boite = (await recherche.boundingBox())!;
	expect(boite.x + boite.width).toBeLessThanOrEqual(page.viewportSize()!.width);

	await recherche.fill('ASCENSEUR');
	await expect(page.locator('#presta-1')).toBeVisible();
	await expect(page.locator('#presta-2')).toHaveCount(0);

	await recherche.fill('helene gerante');
	await expect(page.locator('#presta-2')).toBeVisible();
	await expect(page.locator('#presta-1')).toHaveCount(0);

	await recherche.fill('helene otis');
	await expect(page.getByText('Aucun prestataire pour ces critères')).toBeVisible();

	await recherche.fill('');
	await expect(page.locator('#presta-1')).toBeVisible();
	await expect(page.locator('#presta-2')).toBeVisible();
});

/*
 *  🗂️ Les réglages de la page Affaires (10/10/2026, devenue le standard du site) :
 *  la recherche EN TÊTE, puis la catégorie et le contrat, chaque libellé devant
 *  sa rangée — les « deux lignes » du 28/09 cèdent la place à cette grille.
 */
test('sur ordinateur, la recherche en tête, puis la catégorie et le contrat', async ({
	page,
}, info) => {
	test.skip(info.project.name !== 'bureau', 'la grille à deux colonnes vaut pour un ordinateur');
	await ouvrirAnnuaire(page);
	const haut = async (nom: string) =>
		(await page.getByRole('group', { name: nom, exact: true }).boundingBox())!;
	const type = await haut('Catégorie');
	const contrat = await haut('Contrat');
	const recherche = (await page.getByRole('searchbox', { name: 'Recherche' }).boundingBox())!;

	expect(type.y).toBeGreaterThan(recherche.y + recherche.height - 1);
	expect(contrat.y).toBeGreaterThan(type.y + type.height - 1);
	//  Les champs partent du même bord : la colonne des libellés devant eux.
	expect(Math.abs(type.x - contrat.x)).toBeLessThan(2);
	//  Et rien ne déborde de la page.
	await attendreSansDefilementHorizontal(page);
});
