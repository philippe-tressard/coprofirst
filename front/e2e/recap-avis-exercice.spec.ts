/*
 *  **Le récapitulatif des avis d'un prestataire, par exercice** (maquette R3d, 15/11/2026).
 *
 *  Sur la fiche dépliée, les avis se rangent par exercice comptable — servi par l'API
 *  (`exercice_annee`, `exercice_libelle`) —, le plus récent d'abord, chacun avec son
 *  compte d'états. Le plus récent est ouvert ; un autre se déplie au clic.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

const OTIS = {
	id: 1,
	nom: 'Ascenseurs Témoin',
	specialite: 'ascenseur',
	type_prestataire: 'maintenance_depannage',
	actif: true,
	archivee: false,
};

const avis = (id: number, etat: string, annee: number, jour: string) => ({
	id,
	prestataire_id: 1,
	note: etat === 'mauvais' ? 1 : etat === 'neutre' ? 3 : 5,
	etat,
	exercice_annee: annee,
	exercice_libelle: String(annee),
	commentaire: null,
	contrat_id: null,
	auteur_id: null,
	auteur_nom: null,
	cree_le: `${jour}T10:00:00`,
});

const AVIS = [
	avis(1, 'excellent', 2026, '2026-11-12'),
	avis(2, 'excellent', 2026, '2026-10-03'),
	avis(3, 'mauvais', 2026, '2026-10-21'),
	avis(4, 'neutre', 2025, '2025-06-03'),
];

test('les avis se rangent par exercice, avec le compte de chaque état', async ({ page }) => {
	await simulerApi(page, (api) => {
		if (api === '/api/prestataires') return [OTIS];
		if (api === '/api/prestataires/notations') return AVIS;
	});
	await page.goto('/prestataires');
	await attendreHydratation(page);
	const carte = page.locator('#presta-1');
	await carte.getByText('Ascenseurs Témoin').first().click();

	const exercices = carte.locator('.not-exercice-entete');
	await expect(exercices).toHaveCount(2);
	await expect(exercices.nth(0)).toContainText('Exercice 2026');
	await expect(exercices.nth(0)).toContainText('3 avis');
	await expect(exercices.nth(0)).toContainText('2 Excellent');
	await expect(exercices.nth(0)).toContainText('1 Mauvais');
	await expect(exercices.nth(1)).toContainText('Exercice 2025');

	//  Le plus récent est ouvert, l'autre replié : ses avis ne se voient pas encore.
	await expect(exercices.nth(0)).toHaveAttribute('aria-expanded', 'true');
	await expect(exercices.nth(1)).toHaveAttribute('aria-expanded', 'false');
	await expect(carte.locator('.not-item')).toHaveCount(3);

	await exercices.nth(1).click();
	await expect(exercices.nth(1)).toHaveAttribute('aria-expanded', 'true');
	await expect(carte.locator('.not-item')).toHaveCount(1);
});
