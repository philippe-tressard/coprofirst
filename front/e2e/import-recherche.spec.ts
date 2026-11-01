/*
 *  **Une recherche dans chacun des trois tableaux d'import** (#2173, 23/10/2026).
 *
 *  Demandé : « offrir la possibilité de recherche dans chacun des 3 tableaux ».
 *  Elle vit une fois, dans `BarreImport` — la grille des réglages du site :
 *  Recherche en tête, puis le Statut en pastilles —, et chaque écran filtre ce
 *  que SA ligne montre. Le test l'éprouve sur les lots et sur les badges Vigik
 *  (l'écran d'accès sert aussi les télécommandes), bureau ET téléphone :
 *  tous les mots, sans accents ni casse ; le bilan et « Effacer la recherche » ;
 *  le compteur de la pastille retenue ; aucun défilement horizontal de la page.
 */
import type { Page } from '@playwright/test';
import type { LigneImportLot } from '../src/lib/api';
import { MEMBRE_CS, attendreHydratation, expect, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal, elargirLeTexte } from './defilement';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const lot = (id: number, numero: string, batiment: string, nom: string) =>
	({
		id,
		batiment_id: 1,
		batiment_nom: batiment,
		numero,
		type_raw: 'AP',
		etage_raw: '2',
		no_coproprietaire: `C${id}`,
		nom_coproprietaire: nom,
		statut: 'en_attente',
		lot_id: null,
		lot_label: null,
		utilisateurs: [],
		notes_admin: null,
		importe_le: null,
		resolu_le: null,
	}) as LigneImportLot;

const LOTS = [lot(7, '12', 'Bât. 1', 'DURAND'), lot(8, '14', 'Bât. 2', 'MARTIN')];

const VIGIK = [7, 8].map((id) => ({
	id,
	statut: 'en_attente',
	user_proprietaire_id: null,
	user_locataire_id: null,
	lot_id: null,
	chez_locataire: false,
	refuse_par_locataire: false,
	notes_admin: null,
	importe_le: '2026-10-01T08:00:00Z',
	resolu_le: null,
	nom_proprietaire: id === 7 ? 'DURAND' : 'MARTIN',
	nom_locataire: null,
	batiment_raw: id === 7 ? '1' : '2',
	appartement_raw: '12',
	code: id === 7 ? 'VK-4521' : 'VK-7788',
	proprietaire: null,
	locataire: null,
	lot_label: null,
	lot_porteurs: null,
	rattachable: false,
}));

async function ouvrir(page: Page, source: string) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/lots/admin/imports') return LOTS;
		if (chemin === '/api/lots/admin/imports/stats') return {};
		if (chemin === '/api/acces/admin/imports-vigik') return VIGIK;
		if (chemin === '/api/acces/admin/imports-vigik/stats') return { total: 2 };
	});
	await page.goto(`/admin?onglet=imports&source=${source}`);
	await attendreHydratation(page);
}

test('lots : tous les mots, sans accents ni casse, puis « Effacer la recherche »', async ({
	page,
}) => {
	await ouvrir(page, 'lots');
	const lignes = page.locator('table tbody tr');
	await expect(lignes).toHaveCount(2);

	const champ = page.getByRole('searchbox', { name: 'Recherche' });
	await champ.fill('bat 2 martin');
	await expect(lignes).toHaveCount(1);
	await expect(lignes.first()).toContainText('MARTIN');
	await expect(page.getByRole('status').filter({ hasText: 'pour « bat 2 martin »' })).toContainText(
		'1 ligne',
	);
	//  Le compteur se lit sur la pastille retenue (« Tous »), ux-patterns §5.
	await expect(page.getByRole('group', { name: 'Statut' })).toContainText('1');
	await elargirLeTexte(page);
	await attendreSansDefilementHorizontal(page);

	await page.getByRole('button', { name: 'Effacer la recherche' }).click();
	await expect(champ).toHaveValue('');
	await expect(lignes).toHaveCount(2);
});

test('Vigik : la recherche lit le code et le nom, et dit quand rien ne correspond', async ({
	page,
}) => {
	await ouvrir(page, 'vigik');
	const lignes = page.locator('table tbody tr');
	await expect(lignes).toHaveCount(2);

	const champ = page.getByRole('searchbox', { name: 'Recherche' });
	await champ.fill('vk-4521');
	await expect(lignes).toHaveCount(1);
	await expect(lignes.first()).toContainText('DURAND');

	await champ.fill('introuvable');
	await expect(page.locator('table')).toHaveCount(0);
	await expect(page.getByRole('status').filter({ hasText: 'pour « introuvable »' })).toContainText(
		'0 ligne',
	);
	await elargirLeTexte(page);
	await attendreSansDefilementHorizontal(page);
});
