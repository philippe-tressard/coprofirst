/*
 *  **Une phrase ne se lit pas deux fois en tête d'écran.**
 *
 *  Relevé le 27/09/2026 (#1369) : en tête de *Ma résidence*, « Informations,
 *  plans et documents de la copropriété. » s'affichait DEUX fois, l'une sous
 *  l'autre. Le descriptif de la page — écrit à la main par l'écran, et posé
 *  SOUS les onglets — et celui de l'onglet « Fiche », rendu par `BarreOnglets`,
 *  portaient le même texte.
 *
 *  Depuis, le descriptif de page est rendu par `EntetePage` (au-dessus des
 *  onglets, `lint:entetes` refuse de l'écrire ailleurs) et `BarreOnglets` tait
 *  un descriptif d'onglet identique. Ce test lit ce qu'on VOIT : les deux textes
 *  sont administrables, et seul l'écran rendu dit ce qui s'affiche.
 */
import { expect, simulerApi, test } from './aides';

const PHRASE_RESIDENCE = 'Informations, plans et documents de la copropriété.';

test('Résidence : le descriptif partagé par la page et l’onglet ne s’affiche qu’une fois', async ({
	page,
}) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/copropriete' ? { id: 1, nom: 'Résidence témoin' } : undefined,
	);
	await page.goto('/residence');
	//  Cas zéro : l'écran est bien rendu, onglets compris.
	await expect(page.getByRole('navigation', { name: 'Onglets' })).toBeVisible();
	await expect(page.getByText(PHRASE_RESIDENCE, { exact: true })).toHaveCount(1);
	//  … et au-dessus des onglets, comme sur tous les autres écrans.
	const phrase = await page.getByText(PHRASE_RESIDENCE, { exact: true }).boundingBox();
	const onglets = await page.getByRole('navigation', { name: 'Onglets' }).boundingBox();
	expect(phrase!.y, 'le descriptif de page passe sous les onglets').toBeLessThan(onglets!.y);
});

test('Affaires : un descriptif d’onglet DIFFÉRENT reste affiché sous la rangée', async ({
	page,
}) => {
	await simulerApi(page);
	await page.goto('/tickets');
	await expect(page.locator('.page-subtitle')).toHaveCount(1);
	await expect(page.locator('.tab-descriptif')).toHaveText(
		'Les actualités et les affaires en cours.',
	);
});
