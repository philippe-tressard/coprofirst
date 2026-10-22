/*
 *  **La correction d'une ligne d'import des lots** (#1571, 08/10/2026).
 *
 *  Le formulaire est parti d'`OngletImportLots` dans `CorrectionImportLot` : la
 *  saisie y vit en `bind:` (lot, occupants, note), l'enregistrement reste à
 *  l'onglet. Ce découpage est le seul de la série qui déplace une SAISIE — une
 *  liaison perdue ne lèverait rien, l'appel partirait simplement avec l'ancienne
 *  valeur. Le test lit donc le corps du PATCH, jamais l'écran.
 */
import type { LigneImportLot, MonLot, UtilisateurAdmin } from '../src/lib/api';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const LIGNE = {
	id: 7,
	batiment_id: 1,
	batiment_nom: 'Bât. 1',
	numero: '12',
	type_raw: 'AP',
	etage_raw: '2',
	no_coproprietaire: 'C12',
	nom_coproprietaire: 'DURAND',
	statut: 'en_attente',
	lot_id: null,
	lot_label: null,
	utilisateurs: [
		{
			user_id: 31,
			type_lien: 'propriétaire',
			utilisateur: { id: 31, prenom: 'Anne', nom: 'Durand' },
		},
	],
	notes_admin: null,
	importe_le: null,
	resolu_le: null,
} as LigneImportLot;

const LOTS = [
	{ id: 101, numero: '12', type: 'appartement', batiment_id: 1, batiment_nom: 'Bât. 1' },
] as MonLot[];

const COMPTES = [
	{ id: 31, prenom: 'Anne', nom: 'Durand', email: 'anne@exemple.test' },
	{ id: 32, prenom: 'Paul', nom: 'Martin', email: 'paul@exemple.test' },
] as UtilisateurAdmin[];

test('la correction d’une ligne envoie le lot, les occupants et la note saisis', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/lots/admin/imports') return [LIGNE];
		if (chemin === '/api/lots/admin/imports/stats') return {};
		if (chemin === '/api/lots/admin/tous') return LOTS;
		if (chemin === '/api/admin/utilisateurs') return COMPTES;
		if (chemin === '/api/lots/admin/imports/7') return LIGNE;
	});
	await page.goto('/admin?onglet=imports&source=lots');
	await attendreHydratation(page);

	await page.getByRole('button', { name: 'Modifier' }).first().click();
	const formulaire = page.locator('.imp-edit-form');
	await expect(formulaire).toBeVisible();

	await formulaire.locator('#imp-lot-7').selectOption('101');
	//  Un occupant ajouté, renseigné, puis le premier retiré : les deux gestes
	//  qui ont quitté l'onglet avec le formulaire.
	await formulaire.getByRole('button', { name: '+ Ajouter' }).click();
	await formulaire.locator('.select-user').nth(1).selectOption('32');
	await formulaire.getByRole('button', { name: 'Retirer cet occupant' }).first().click();
	await formulaire.locator('#imp-notes-7').fill('vérifié au registre');

	const envoi = page.waitForRequest(
		(r) => r.method() === 'PATCH' && new URL(r.url()).pathname === '/api/lots/admin/imports/7',
	);
	await formulaire.getByRole('button', { name: 'Enregistrer' }).click();
	expect((await envoi).postDataJSON()).toEqual({
		lot_id: 101,
		utilisateurs: [{ user_id: 32, type_lien: 'locataire' }],
		notes_admin: 'vérifié au registre',
	});
});
