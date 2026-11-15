/*
 *  **La légende des bâtiments du kanban d'accueil** (16/11/2026) : sous le titre,
 *  une ligne discrète rappelle la couleur de chaque bâtiment, « Bât. 1 (D) » à
 *  « Bât. 4 (A) ».
 *
 *  Ce qui se prouve ici, et que la relecture ne voit pas :
 *  - les libellés sont ceux que l'API SERT (`batiment_libelle`, lettre de l'acte
 *    comprise), dans l'ordre de l'arbre ;
 *  - seuls les BÂTIMENTS y sont — un espace de tête (le parking) n'en est pas ;
 *  - la pastille de la légende a la couleur de la pastille de la brique : les deux
 *    passent par `couleurPerimetre`, une divergence ferait mentir la légende.
 *  Données fictives.
 */
import type { Perimetre } from '../src/lib/perimetres';
import { noeud } from './perimetres-temoins';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const LETTRES = ['D', 'C', 'B', 'A'];

const ARBRE: Perimetre[] = [
	noeud({ id: 1, code: 'résidence', libelle: 'Résidence', par_defaut: true, concerne_tous: true }),
	noeud({ id: 2, code: 'batiments', libelle: 'Bâtiments', selectionnable: false, ordre: 1 }),
	...LETTRES.map((lettre, i) =>
		noeud({
			id: 10 + i,
			code: `bat:${i + 1}`,
			parent: 'batiments',
			libelle: `Bâtiment ${i + 1}`,
			libelle_court: `Bât. ${i + 1}`,
			batiment_id: i + 1,
			batiment_libelle: `Bât. ${i + 1} (${lettre})`,
			ordre: i,
		}),
	),
	noeud({ id: 20, code: 'parking', libelle: 'Parking', ordre: 2 }),
];

const AFFAIRE = {
	id: 7,
	numero: 'TK-124301',
	titre: 'Porte du hall',
	description: 'La gâche ne tient plus.',
	categorie: 'panne',
	categorie_libelle: 'Panne',
	statut: 'ouvert',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['bat:1'],
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	suivi_kanban: true,
	colonne_kanban: 'syndic',
	natures: ['activite'],
	cree_le: '2026-09-20T10:00:00',
	mis_a_jour_le: '2026-09-20T10:00:00',
};

test.use({ viewport: { width: 1400, height: 900 } });

test('la légende nomme chaque bâtiment servi, dans l’ordre, avec la couleur de ses briques', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/perimetres') return ARBRE;
		if (chemin === '/api/tickets') return [AFFAIRE];
	});
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);

	const legende = page.getByLabel('Couleur de chaque bâtiment');
	const cles = legende.locator('.graphique-cle');
	await expect(cles).toHaveText(['Bât. 1 (D)', 'Bât. 2 (C)', 'Bât. 3 (B)', 'Bât. 4 (A)']);
	await expect(legende).not.toContainText('Parking');

	//  La pastille de la légende et celle de la brique ont la même couleur RENDUE.
	const fond = (l: import('@playwright/test').Locator) =>
		l.evaluate((e) => getComputedStyle(e).backgroundColor);
	const brique = page.locator('.kanban-card', { hasText: AFFAIRE.titre }).locator('.kb-tag');
	await expect(brique).toHaveText('Bât. 1');
	expect(await fond(cles.first().locator('.graphique-pastille'))).toBe(await fond(brique));
	//  …et deux bâtiments ne se confondent pas.
	expect(await fond(cles.nth(0).locator('.graphique-pastille'))).not.toBe(
		await fond(cles.nth(1).locator('.graphique-pastille')),
	);
});
