/*
 *  **Le locataire dit ce qu'il loue** — trois questions dans « Mes lots » (04/10/2026).
 *
 *  Son propriétaire n'a pas de compte : les lots viennent du fichier du syndic
 *  (`/lots/ma-location/propositions`). Chaque « Oui » rattache le lot ; le
 *  bouton attend une réponse à chaque question posée, et n'envoie QUE les lots
 *  retenus. La règle et ses bornes sont tenues côté serveur
 *  (`api/tests/test_rattachement_locataire.py`) ; ce test-ci tient l'écran.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const LOCATAIRE = { ...MEMBRE_CS, statut: 'locataire', role: 'résident', roles: ['résident'] };

//  Le type en clair est SERVI par l'API (`libelle_type`, #2507) : le simulé le porte.
const LIBELLES: Record<string, string> = {
	appartement: 'Appartement',
	cave: 'Cave',
	parking: 'Parking',
};

const lot = (id: number, numero: string, type: string, acces: Record<string, number>) => ({
	id,
	numero,
	type,
	libelle_type: LIBELLES[type],
	type_appartement: null,
	etage: null,
	superficie: null,
	batiment_id: type === 'parking' ? null : 4,
	batiment_nom: type === 'parking' ? null : 'Bât. 4',
	est_logement_de_reference: false,
	type_lien: null,
	acces,
});

const PROPOSITIONS = {
	proprietaire: 'DURANDAL',
	appartement: [lot(13, '13', 'appartement', { vigik: 1, telecommande: 0 })],
	cave: [lot(408, '408', 'cave', { vigik: 0, telecommande: 0 })],
	parking: [lot(462, '462', 'parking', { vigik: 0, telecommande: 1 })],
};

test('trois questions, puis seuls les lots retenus partent', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return LOCATAIRE;
		if (chemin === '/api/lots/ma-location/propositions') return PROPOSITIONS;
		if (chemin === '/api/lots/ma-location') return { lots: 2, vigik: 1, telecommande: 1 };
	});
	await page.goto('/mon-lot');

	const appartement = page.getByRole('radiogroup', { name: /Résidez-vous dans l’appartement/ });
	const cave = page.getByRole('radiogroup', { name: /une cave/ });
	const parking = page.getByRole('radiogroup', { name: /place de parking/ });
	await expect(appartement, 'la question de l’appartement n’est pas posée').toContainText('Oui');
	await expect(appartement).toHaveAccessibleName(/appartement 13 \(Bât\. 4\)/);

	const enregistrer = page.getByRole('button', { name: 'Enregistrer' });
	await appartement.getByText('Oui', { exact: true }).click();
	await cave.getByText('Non', { exact: true }).click();
	await expect(enregistrer, 'une question reste sans réponse').toBeDisabled();
	await parking.getByText('Oui', { exact: true }).click();
	await expect(page.getByRole('checkbox', { name: /Parking 462/ })).toBeChecked();
	await expect(page.getByText('1 télécommande')).toBeVisible();

	const requete = page.waitForRequest(
		(r) => r.method() === 'POST' && r.url().endsWith('/api/lots/ma-location'),
	);
	await enregistrer.click();
	expect((await requete).postDataJSON()).toEqual({ lot_ids: [13, 462] });
});
