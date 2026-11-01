/*
 *  **La consommation de l'assistant IA se lit dans l'onglet Maintenance (#1383).**
 *
 *  Rien ne comptait les appels à l'assistant, dont un usage automatique. Ce test
 *  rend le VRAI onglet, API simulée, et lit ce qu'un administrateur voit : la
 *  jauge de la limite d'appels du mois (04/10/2026), le mois avec son coût estimé, et — c'est la promesse qui
 *  compte — un mois sans tarif qui dit « coût non renseigné » au lieu d'un 0 €.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal } from './defilement';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const LIGNE = {
	usage: 'reponse_courriel',
	libelle: 'Mise en forme des réponses par courriel',
	modele: 'gpt-4o-mini',
	appels: 412,
	erreurs: 3,
	refus: 0,
	jetons_entree: 820000,
	jetons_sortie: 164000,
};

const CONSOMMATION = {
	mois_courant: '2026-09',
	limites: [
		{
			usage: 'reponse_courriel',
			libelle: LIGNE.libelle,
			appels_mois: 500,
			appels_heure: 0,
			appels: 490,
			premier_essai: null,
		},
		{
			usage: 'description',
			libelle: 'Rédaction d’une description',
			appels_mois: 0,
			appels_heure: 5,
			appels: 12,
			premier_essai: null,
		},
	],
	mois: [
		{ mois: '2026-09', usages: [{ ...LIGNE, jetons_cache: 512000, cout_usd: '0.2200' }] },
		{ mois: '2026-08', usages: [{ ...LIGNE, jetons_cache: 0, cout_usd: null }] },
	],
};

test('Maintenance : la consommation de l’assistant, sa limite et son coût', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/llm-consommation') return CONSOMMATION;
		return undefined;
	});
	await page.goto('/admin?onglet=maintenance');

	const carte = page.locator('section.config-section', {
		has: page.getByText('Consommation de l’assistant IA', { exact: true }),
	});
	await expect(carte).toBeVisible();

	//  La jauge : seul l'usage limité au mois en a une, et elle passe à l'alerte à 98 %.
	await expect(carte.getByRole('progressbar')).toHaveCount(1);
	await expect(carte.getByText(/490 \/ 500 appels/)).toBeVisible();
	await expect(carte.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '98');
	await expect(carte.locator('.jauge-alerte')).toHaveCount(1);

	//  Le coût : estimé quand il y a un tarif, TU quand il n'y en a pas.
	await expect(carte.getByText(/0,22\s\$US estimés/)).toBeVisible();
	//  La part lue en cache se dit, quand il y en a une.
	await expect(carte.getByText(/dont 512\s000 en cache/)).toBeVisible();
	await expect(carte.getByText('coût non renseigné')).toHaveCount(1);
	await expect(carte.getByText('3 en échec').first()).toBeVisible();

	await attendreSansDefilementHorizontal(page, 'dans l’onglet Maintenance');

	await carte.screenshot({
		path: `test-results/consommation-ia-${test.info().project.name}.png`,
	});
});
