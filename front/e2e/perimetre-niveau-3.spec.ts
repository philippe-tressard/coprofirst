/*
 *  **Le sélecteur de périmètre descend au niveau 3, pas au-delà** (10/11/2026).
 *  Demandé : « autoriser un niveau 3 similaire au niveau précédent » — Bâtiment 1
 *  › Logement › Terrasses Balcons. La règle est pure (`#lib/perimetres/selection`) ;
 *  ce qui ne se voit qu'à l'écran est la seconde rangée, son chevron et le résumé
 *  porté par les pastilles du chemin.
 */
import type { Page } from '@playwright/test';
import type { Perimetre } from '../src/lib/perimetres';
import { noeud } from './perimetres-temoins';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const ARBRE: Perimetre[] = [
	noeud({ id: 1, code: 'résidence', libelle: 'Résidence', portee_globale: true, par_defaut: true }),
	noeud({ id: 2, code: 'batiments', libelle: 'Bâtiments', selectionnable: false, ordre: 1 }),
	noeud({ id: 3, code: 'bat:1', libelle: 'Bâtiment 1', parent: 'batiments', batiment_id: 1 }),
	noeud({ id: 4, code: 'bat:1/logement', libelle: 'Logement', parent: 'bat:1', ordre: 0 }),
	noeud({ id: 5, code: 'bat:1/jardin', libelle: 'Jardin', parent: 'bat:1', ordre: 1 }),
	noeud({
		id: 6,
		code: 'bat:1/logement/terrasses',
		libelle: 'Terrasses Balcons',
		libelle_court: 'Terrasses',
		parent: 'bat:1/logement',
	}),
	//  Un niveau 4 écrit avant la règle : le sélecteur ne l'ouvre pas.
	noeud({
		id: 7,
		code: 'bat:1/logement/terrasses/garde-corps',
		libelle: 'Garde-corps',
		parent: 'bat:1/logement/terrasses',
	}),
];

async function nouvelleAffaire(page: Page) {
	await simulerApi(page, (chemin) => (chemin === '/api/perimetres' ? ARBRE : undefined));
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();
	await page
		.getByText(/Ascenseur, chauffage, éclairage/)
		.first()
		.click();
	return page.getByRole('group', { name: /^Nouvelle affaire$/ });
}

test('une rangée de niveau 3 s’ouvre sous un niveau 2, et pas de niveau 4', async ({ page }) => {
	const formulaire = await nouvelleAffaire(page);
	const precision = formulaire.locator('.perimetre-precision');

	await formulaire.getByRole('button', { name: /^Bâtiment 1/ }).click();
	await expect(precision).toHaveText([/Préciser dans Bâtiment 1/]);

	const logement = formulaire.getByRole('button', { name: /^Logement/ });
	await expect(logement.locator('.pastille-chevron')).toHaveCount(1);
	await logement.click();
	await expect(precision).toHaveText([/Préciser dans Bâtiment 1/, /Préciser dans Logement/]);

	const terrasses = formulaire.getByRole('button', { name: /^Terrasses Balcons/ });
	await expect(terrasses.locator('.pastille-chevron')).toHaveCount(0);
	await terrasses.click();
	await expect(terrasses).toHaveClass(/active/);
	await expect(logement).toHaveClass(/active/);
	await expect(logement).toContainText('› Terrasses');
	await expect(formulaire.getByRole('button', { name: /^Bâtiment 1/ })).toContainText(
		'› Logement › Terrasses',
	);
	//  Le niveau 4 ne se propose jamais.
	await expect(precision).toHaveCount(2);
	await expect(formulaire.getByRole('button', { name: /Garde-corps/ })).toHaveCount(0);
	await page.screenshot({ path: test.info().outputPath('niveau-3.png') });

	//  Revenir sur « Logement » ne perd pas « Terrasses » : on vient le revoir.
	await logement.click();
	await expect(terrasses).toHaveClass(/active/);
});
