/*
 *  **Télémétrie : comptes dormants et retour des arrivants** (#1629).
 *
 *  La section dit combien de comptes n'ont plus de visite depuis 60 et 90 jours,
 *  QUI ils sont (l'onglet est réservé à l'administrateur), et la part des
 *  arrivants revenus dans les 7 jours suivant leur validation. Un compte jamais
 *  revenu ne reçoit pas de date inventée : la ligne le dit.
 */
import type { Page } from '@playwright/test';
import {
	attendreHydratation,
	deplierSectionTelemetrie,
	expect,
	MEMBRE_CS,
	simulerApi,
	TABLEAU_TELEMETRIE_VIDE,
	test,
} from './aides';
import { attendreLisible, forcerTheme } from './contraste-ecran';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const RETOUR = {
	comptes_mesures: 8,
	refus: 1,
	dormants: [
		{ seuil: 60, nombre: 2 },
		{ seuil: 90, nombre: 1 },
	],
	liste_dormants: [
		{ user_id: 3, nom: 'Elise FAURE', type: 'Locataire', derniere_visite: null, jours: 100 },
		{
			user_id: 2,
			nom: 'Bruno DURAND',
			type: 'Copropriétaire résident',
			derniere_visite: '2026-08-04',
			jours: 61,
		},
	],
	arrivants: {
		periode: '30 derniers jours',
		fenetre_jours: 7,
		valides: 3,
		revenus: 1,
		jamais_revenus: 1,
		en_attente: 1,
		taux: 50,
	},
};

async function ouvrir(page: Page, retour: unknown = RETOUR) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/telemetry/dashboard') return { ...TABLEAU_TELEMETRIE_VIDE, retour };
	});
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);
}

test('dormants par seuil, liste nominative et retour des arrivants', async ({ page }) => {
	await ouvrir(page);
	const section = await deplierSectionTelemetrie(page, 'Comptes dormants et arrivants');

	await expect(section.getByRole('row', { name: /60 jours ou plus\s+2 \/ 8/ })).toBeVisible();
	await expect(section.getByRole('row', { name: /90 jours ou plus\s+1 \/ 8/ })).toBeVisible();

	const durand = section.getByRole('row', { name: /Bruno DURAND/ });
	await expect(durand).toContainText('4 août 2026');
	await expect(durand).toContainText('61');
	//  Jamais revenu : aucune date inventée.
	await expect(section.getByRole('row', { name: /Elise FAURE/ })).toContainText(
		'aucune depuis la validation',
	);

	await expect(section.getByRole('row', { name: /Taux de retour\s+50 %/ })).toBeVisible();
	await expect(section.getByText('1 compte a refusé la mesure d’audience')).toBeVisible();
});

test('aucun compte mesuré : la section ne se déplie pas', async ({ page }) => {
	await ouvrir(page, { ...RETOUR, comptes_mesures: 0, liste_dormants: [] });
	const titre = page.getByRole('heading', { name: /Comptes dormants et arrivants/ });
	await expect(titre).toContainText('aucun compte mesuré');
	await expect(page.locator('details', { hasText: 'Comptes dormants et arrivants' })).toHaveCount(
		0,
	);
});

test('@sombre — Télémétrie : les tableaux des comptes dormants et des arrivants se lit au thème sombre', async ({
	page,
}) => {
	await ouvrir(page);
	await deplierSectionTelemetrie(page, 'Comptes dormants et arrivants');
	await forcerTheme(page, 'sombre');
	await attendreLisible(page, '#contenu');
});
