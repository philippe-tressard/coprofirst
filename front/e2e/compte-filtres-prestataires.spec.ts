/*
 *  **Le compteur de filtre vaut pour tout le site, pas pour les seules
 *  Affaires** (10/10/2026, standard de la maquette J).
 *
 *  `compte-filtres-affaires` éprouve le composant ; celui-ci éprouve qu'un
 *  AUTRE écran lui donne le bon nombre — l'annuaire des prestataires, qui pose
 *  deux rangées (métier, contrat) sur une liste dont les Archives sont à part :
 *
 *  1. chaque rangée porte le compte sur sa pastille retenue, et sur elle seule ;
 *  2. ce compte est celui des cartes affichées ;
 *  3. une fiche archivée n'est pas comptée : les Archives ont leur vignette.
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';

const prestataire = (id: number, nom: string, type: string, archivee = false) => ({
	id,
	nom,
	specialite: 'ascenseur',
	type_prestataire: type,
	actif: !archivee,
	archivee,
});

async function ouvrir(page: Page, baseURL: string | undefined) {
	//  `/prestataires` a une garde SERVEUR qui ne regarde que la PRÉSENCE du cookie.
	await page.context().addCookies([{ name: 'access_token', value: 'temoin', url: baseURL }]);
	await simulerApi(page, (api) => {
		if (api === '/api/prestataires')
			return [
				prestataire(1, 'Otis', 'maintenance_depannage'),
				prestataire(2, 'Kone', 'maintenance_depannage'),
				prestataire(4, 'Cabinet Ravel', 'reglementaire'),
			];
		if (api === '/api/prestataires/archives')
			return [prestataire(3, 'Sicli', 'maintenance_depannage', true)];
	});
	await page.goto('/prestataires');
}

const rangee = (page: Page, libelle: string) =>
	page.getByRole('group', { name: libelle, exact: true });
const comptes = (page: Page, libelle: string) => rangee(page, libelle).locator('.compte');

test('annuaire : la pastille retenue de chaque rangée compte les fiches affichées', async ({
	page,
	baseURL,
}) => {
	await ouvrir(page, baseURL);
	await expect(page.locator('#presta-1')).toBeVisible(); //  cas zéro

	//  « Tous » retenu dans les deux rangées : trois fiches, l'archivée à part.
	for (const libelle of ['Catégorie', 'Contrat']) {
		await expect(comptes(page, libelle)).toHaveCount(1);
		await expect(comptes(page, libelle)).toHaveText('3');
		await expect(
			rangee(page, libelle).getByRole('button', { name: /^Tous/ }).locator('.compte'),
		).toHaveCount(1);
	}

	//  Retenir un métier : sa pastille prend le compte, l'autre rangée suit.
	const maintenance = rangee(page, 'Catégorie').getByRole('button', {
		name: /Maintenance/,
	});
	await maintenance.click();
	await expect(maintenance.locator('.compte')).toHaveText('2');
	await expect(comptes(page, 'Catégorie')).toHaveCount(1);
	await expect(comptes(page, 'Contrat')).toHaveText('2');
	await expect(page.locator('[id^="presta-"]')).toHaveCount(2);
});
