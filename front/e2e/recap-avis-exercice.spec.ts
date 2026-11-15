/*
 *  **Le récapitulatif des avis d'un prestataire, par intervention** (maquette R3d, 15/11/2026).
 *
 *  Sur la fiche dépliée, un bloc par exercice comptable — servi par l'API
 *  (`GET /prestataires/{id}/interventions`) — : « 2 interventions · 1 notée », le compte
 *  des états, puis une ligne par affaire avec le badge de chaque avis (« non notée »
 *  sinon). Le plus récent est ouvert. Un badge déplie l'avis, sous sa ligne ; son auteur
 *  le corrige, et les cases qu'il avait cochées sont RECOCHÉES.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const OTIS = {
	id: 1,
	nom: 'Ascenseurs Témoin',
	specialite: 'ascenseur',
	type_prestataire: 'maintenance_depannage',
	actif: true,
	archivee: false,
};

const avis = (id: number, etat: string, annee: number, jour: string, ticket: number | null) => ({
	id,
	prestataire_id: 1,
	note: etat === 'mauvais' ? 1 : etat === 'neutre' ? 3 : 5,
	etat,
	exercice_annee: annee,
	exercice_libelle: String(annee),
	ticket_id: ticket,
	ticket_titre: null,
	peut_modifier: id === 1,
	commentaire: id === 1 ? 'Points forts : délai respecté.\nTrès réactif.' : null,
	contrat_id: null,
	auteur_id: null,
	auteur_nom: null,
	cree_le: `${jour}T10:00:00`,
});

const AVIS = [
	avis(1, 'excellent', 2026, '2026-11-12', 42),
	avis(2, 'mauvais', 2026, '2026-10-21', 42),
	avis(3, 'neutre', 2026, '2026-10-03', null),
	avis(4, 'neutre', 2025, '2025-06-03', 40),
];

const intervention = (id: number, titre: string, jour: string, lesAvis: typeof AVIS) => ({
	ticket_id: id,
	numero: `TK-0000${id}`,
	titre,
	date: `${jour}T09:00:00`,
	avis: lesAvis,
});

const INTERVENTIONS = [
	{
		annee: 2026,
		libelle: '2026',
		nb_interventions: 2,
		nb_notees: 1,
		compte: { mauvais: 1, neutre: 1, excellent: 1 },
		interventions: [
			intervention(42, 'Porte du hall bloquée', '2026-10-01', [AVIS[0], AVIS[1]]),
			intervention(41, 'Bouton d’appel du 3e', '2026-09-15', []),
		],
		avis_generaux: [AVIS[2]],
	},
	{
		annee: 2025,
		libelle: '2025',
		nb_interventions: 1,
		nb_notees: 1,
		compte: { mauvais: 0, neutre: 1, excellent: 0 },
		interventions: [intervention(40, 'Révision annuelle', '2025-05-20', [AVIS[3]])],
		avis_generaux: [],
	},
];

async function ouvrirLaFiche(page: Page) {
	await simulerApi(page, (api) => {
		if (api === '/api/prestataires') return [OTIS];
		if (api === '/api/prestataires/notations') return AVIS;
		if (api === '/api/prestataires/1/interventions') return INTERVENTIONS;
		if (api === '/api/prestataires/affaires-a-noter') return [];
	});
	await page.goto('/prestataires');
	await attendreHydratation(page);
	const carte = page.locator('#presta-1');
	await carte.getByText('Ascenseurs Témoin').first().click();
	return carte;
}

test('les interventions se rangent par exercice, notées ou non', async ({ page }) => {
	const carte = await ouvrirLaFiche(page);

	const exercices = carte.locator('.not-exercice-entete');
	await expect(exercices).toHaveCount(2);
	await expect(exercices.nth(0)).toContainText('Exercice 2026');
	await expect(exercices.nth(0)).toContainText('2 interventions');
	await expect(exercices.nth(0)).toContainText('1 notée');
	await expect(exercices.nth(0)).toContainText('1 Excellent');
	await expect(exercices.nth(0)).toContainText('1 Mauvais');
	await expect(exercices.nth(1)).toContainText('Exercice 2025');

	//  Le plus récent est ouvert : ses deux affaires et la ligne des avis sans affaire.
	await expect(exercices.nth(0)).toHaveAttribute('aria-expanded', 'true');
	await expect(exercices.nth(1)).toHaveAttribute('aria-expanded', 'false');
	const lignes = carte.locator('.not-item');
	await expect(lignes).toHaveCount(3);
	await expect(lignes.nth(0)).toContainText('Porte du hall bloquée');
	await expect(lignes.nth(1)).toContainText('non notée');
	await expect(lignes.nth(2)).toContainText('Avis sans affaire');

	await exercices.nth(1).click();
	await expect(exercices.nth(1)).toHaveAttribute('aria-expanded', 'true');
	await expect(lignes).toHaveCount(1);
});

test('corriger son avis recoche les cases, et le formulaire s’ouvre sous la ligne', async ({
	page,
}) => {
	const carte = await ouvrirLaFiche(page);

	await carte.getByRole('button', { name: /^Excellent — afficher/ }).click();
	const detail = carte.locator('.not-detail');
	await expect(detail).toContainText('Très réactif.');
	await detail.getByRole('button', { name: 'Modifier cet avis' }).click();

	await expect(detail.getByLabel('délai respecté')).toBeChecked();
	await expect(detail.getByLabel('travail soigné')).not.toBeChecked();
	await expect(detail.getByLabel('Commentaire libre')).toHaveValue('Très réactif.');
	//  Sur toute la largeur de la ligne, et non tassé entre la date et les boutons.
	const largeurLigne = (await carte.locator('.not-item').first().boundingBox())?.width ?? 0;
	const largeurDetail = (await detail.boundingBox())?.width ?? 0;
	expect(largeurDetail).toBeGreaterThan(largeurLigne * 0.9);
});
