/*
 *  **« Mes lots » : les caractéristiques, le sélecteur, le bail, la suppression**
 *  (#779, 01/10/2026).
 *
 *  Ce que le lot a réuni, tenu par ce que l'utilisateur VOIT :
 *
 *  - le copropriétaire choisit son lot dans des pastilles (`ChoixPastilles`) ;
 *    le type s'y lit tel que l'API le sert (`libelle_type`, #2507) — « Local
 *    commercial », et non « Local_commercial », que la capitale posée à la main donnait ;
 *  - les caractéristiques passent par `CaracteristiquesLot` ;
 *  - le locataire voit l'état de son bail par `BadgeStatutBail` : un bail en
 *    cours de sortie n'est plus « vert » ;
 *  - supprimer un bail ou un compte passe par la confirmation partagée, rouge,
 *    qui dit « irréversible » — et n'envoie rien tant qu'on n'a pas confirmé.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, boiteStable, expect, MEMBRE_CS, simulerApi, test } from './aides';
import { nomServi } from './noms-servis';

const LOTS = [
	{
		id: 1,
		numero: '12',
		batiment_nom: 'Bât. 2',
		type: 'appartement',
		type_appartement: 'T3',
		etage: 2,
		superficie: 64,
		libelle_type: 'Appartement',
		libelle_type_complet: 'Appartement – T3',
	},
	{
		id: 2,
		numero: '40',
		batiment_nom: 'Bât. 2',
		type: 'local_commercial',
		etage: 0,
		libelle_type: 'Local commercial',
		libelle_type_complet: 'Local commercial',
	},
];

const BAIL = {
	id: 7,
	lot_id: 1,
	statut: 'actif',
	locataire_id: 55,
	locataire_prenom: 'Paul',
	locataire_nom: 'Durand',
	locataire_nom_affiche: nomServi({ prenom: 'Paul', nom: 'Durand' }),
	locataire_email: 'paul@exemple.test',
	date_entree: '2026-01-01',
	objets: [],
};

/**  Les requêtes d'écriture envoyées — pour prouver qu'une confirmation
 *   refusée n'envoie RIEN. */
function suivreEcritures(page: Page): string[] {
	const vues: string[] = [];
	page.on('request', (r) => {
		const url = new URL(r.url());
		if (url.pathname.startsWith('/api/') && r.method() !== 'GET') {
			vues.push(`${r.method()} ${url.pathname}`);
		}
	});
	return vues;
}

test('le copropriétaire choisit son lot dans des pastilles, au bon libellé', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/lots/mes-lots' ? LOTS : undefined));
	await page.goto('/mon-lot');
	await attendreHydratation(page);

	const commercial = page.getByRole('button', { name: /Local commercial - 40/ });
	await expect(commercial).toBeVisible();
	await expect(page.getByText('Local_commercial')).toHaveCount(0);

	const fiche = page.locator('.carte-lot');
	await expect(fiche).toContainText('64 m²');
	await commercial.click();
	await expect(fiche).toContainText('40');
	await expect(fiche).not.toContainText('Superficie');
});

test('le locataire voit l’état de son bail par la table des états', async ({ page }) => {
	const LOCATAIRE = {
		...MEMBRE_CS,
		id: 55,
		statut: 'locataire',
		role: 'résident',
		roles: ['résident'],
	};
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return LOCATAIRE;
		if (chemin === '/api/lots/mes-lots') return [];
		if (chemin === '/api/bailleur/mon-bail')
			return {
				...BAIL,
				statut: 'en_cours_sortie',
				lot_numero: '12',
				lot_batiment_nom: 'Bât. 2',
				lot_type: 'appartement',
				lot_etage: 2,
				//  Servi par l'API (`lot_etage_libelle`, #2633) : l'écran le lit.
				lot_etage_libelle: '2ème',
			};
	});
	await page.goto('/mon-lot');
	await attendreHydratation(page);

	await expect(page.getByText('🏠 Lot loué')).toBeVisible();
	const badge = page.locator('.badge', { hasText: 'En cours de sortie' });
	await expect(badge).toBeVisible();
	await expect(badge).toHaveClass(/badge-yellow/);
	await expect(page.getByText('en_cours sortie')).toHaveCount(0);
	await expect(page.locator('dl')).toContainText('Étage');
	await expect(page.locator('dl')).toContainText('2ème');
});

test('supprimer un bail : confirmation partagée, rien n’est envoyé sans elle', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/lots/mes-lots') return LOTS;
		//  Un CS copropriétaire lit SES baux (`lireBaux`), un CS seul les lit tous.
		if (chemin === '/api/bailleur/mes-baux' || chemin === '/api/bailleur/tous-les-baux')
			return [BAIL];
	});
	const ecritures = suivreEcritures(page);
	await page.goto('/mon-lot/location');
	await attendreHydratation(page);

	await page
		.getByRole('button', { name: /Supprimer/ })
		.first()
		.click();
	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('Cette action est irréversible.');
	await expect(boite).toContainText('Paul');
	//  Le message et les boutons ne touchent pas les bords de la boîte : la
	//  confirmation partagée les posait à nu, sans `.modal-body`.
	//  Mesuré À L'ARRÊT : la boîte entre en 200 ms à 96 %, et sa marge de 12 px en
	//  valait 11,5 en cours de route (#1625, un rejeu sur trente).
	const cadre = await boiteStable(boite);
	const message = await boiteStable(boite.locator('.confirmation-message'));
	const annuler = await boiteStable(boite.getByRole('button', { name: 'Annuler' }));
	expect(message!.x - cadre!.x, 'marge gauche du message').toBeGreaterThanOrEqual(12);
	expect(annuler!.x - cadre!.x, 'marge gauche des boutons').toBeGreaterThanOrEqual(12);
	await boite.getByRole('button', { name: 'Annuler' }).click();
	await expect(boite).toHaveCount(0);
	expect(ecritures).toEqual([]);

	await page
		.getByRole('button', { name: /Supprimer/ })
		.first()
		.click();
	await page.getByRole('dialog').getByRole('button', { name: 'Supprimer' }).click();
	await expect.poll(() => ecritures).toContain('DELETE /api/bailleur/baux/7');
});

test('supprimer un compte : la même confirmation', async ({ page }) => {
	const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
	const COMPTE = {
		id: 21,
		prenom: 'Jeanne',
		nom: 'Martin',
		nom_affiche: nomServi({ prenom: 'Jeanne', nom: 'Martin' }),
		email: 'jeanne@exemple.test',
		statut: 'copropriétaire_résident',
		role: 'résident',
		roles: ['résident'],
		actif: true,
		batiment_id: null,
	};
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/utilisateurs') return [COMPTE];
	});
	const ecritures = suivreEcritures(page);
	await page.goto('/admin?onglet=utilisateurs');
	await attendreHydratation(page);

	await page.getByRole('button', { name: 'Supprimer' }).first().click();
	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('jeanne@exemple.test');
	await expect(boite).toContainText('Cette action est irréversible.');
	await boite.getByRole('button', { name: 'Supprimer' }).click();
	await expect.poll(() => ecritures).toContain('DELETE /api/admin/utilisateurs/21');
});
