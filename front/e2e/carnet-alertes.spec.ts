/*
 *  **L'encart des visites en retard du carnet d'entretien** (#1716) — il NOMME
 *  les entrées qu'il annonce, au lieu d'un simple compte.
 *
 *  Ce que ce test tient, et qu'aucun contrôle de source ne verrait :
 *
 *  1. chaque entrée en alerte est listée dans l'encart, avec son équipement et
 *     son retard ; une entrée sans alerte n'y est pas ;
 *  2. le conseil reçoit un lien vers chacune ; un copropriétaire n'en reçoit pas
 *     pour un CONTRAT (les prestataires lui sont fermés), mais bien pour une
 *     intervention ;
 *  3. au bureau comme au téléphone, la page ne défile pas en largeur.
 */
import type { Page } from '@playwright/test';
import type { Carnet, EntreeCarnet } from '../src/lib/api/patrimoine';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ENTREE: EntreeCarnet = {
	date: '2026-03-01',
	libelle: '',
	origine: 'intervention',
	detail: '',
	categorie: null,
	equipement: null,
	perimetre: [],
	lien: '',
	alerte: null,
	extrait: '',
};

const CARNET: Carnet = {
	total: 3,
	entrees: [
		{
			...ENTREE,
			libelle: 'Contrat ascenseur Témoin',
			origine: 'contrat',
			lien: '/prestataires/contrats/7',
			alerte: 'visite attendue depuis 40 jours',
		},
		{
			...ENTREE,
			libelle: 'Ramonage des conduits',
			lien: '/interventions/12',
			alerte: 'visite attendue depuis 12 jours',
		},
		{
			...ENTREE,
			libelle: 'Peinture du hall',
			lien: '/interventions/13',
			extrait: '<p>Les murs du hall sont écaillés.</p>',
		},
	],
};

const PROPRIETAIRE = { ...MEMBRE_CS, role: 'propriétaire', roles: ['propriétaire'] };

async function ouvrir(page: Page, moi = MEMBRE_CS) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return moi;
		if (chemin === '/api/carnet-entretien') return CARNET;
	});
	await page.goto('/residence/carnet');
	await attendreHydratation(page);
	return page.locator('ul.concernees');
}

test.beforeEach(async ({ page }, info) => {
	//  Le téléphone le plus étroit que le site s'engage à tenir.
	if (info.project.name === 'mobile') await page.setViewportSize({ width: 375, height: 812 });
});

test('l’encart nomme chaque visite en retard, et elle seule', async ({ page }) => {
	const liste = await ouvrir(page);
	await expect(page.getByText(/2 visites attendues/)).toBeVisible();
	await expect(liste.locator('li')).toHaveCount(2);
	await expect(liste).toContainText('Contrat ascenseur Témoin');
	await expect(liste).toContainText('visite attendue depuis 40 jours');
	await expect(liste).toContainText('Ramonage des conduits');
	await expect(liste).not.toContainText('Peinture du hall');
	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'défilement horizontal de la page').toBe(false);
});

test('le conseil reçoit un lien vers chaque entrée, contrat compris', async ({ page }) => {
	const liste = await ouvrir(page);
	await expect(liste.getByRole('link', { name: 'Contrat ascenseur Témoin' })).toHaveAttribute(
		'href',
		'/prestataires/contrats/7',
	);
	await expect(liste.getByRole('link', { name: 'Ramonage des conduits' })).toHaveAttribute(
		'href',
		'/interventions/12',
	);
});

test('un copropriétaire lit le contrat sans lien, l’intervention avec', async ({ page }) => {
	const liste = await ouvrir(page, PROPRIETAIRE);
	//  Cas zéro : le contrat est bien nommé — seul le lien manque.
	await expect(liste).toContainText('Contrat ascenseur Témoin');
	await expect(liste.getByRole('link', { name: 'Contrat ascenseur Témoin' })).toHaveCount(0);
	await expect(liste.getByRole('link', { name: 'Ramonage des conduits' })).toHaveCount(1);
});

test('la carte montre l’extrait sous le titre, et seulement s’il existe', async ({ page }) => {
	await ouvrir(page);
	//  « Ce qui s'est passé » ou la demande : le serveur a choisi, l'écran rend.
	const apercus = page.locator('.carte-preview');
	//  Cas zéro : les deux entrées sans extrait n'ont pas d'aperçu vide.
	await expect(apercus).toHaveCount(1);
	await expect(apercus).toHaveText('Les murs du hall sont écaillés.');
	await expect(apercus).toHaveClass(/clamp-3/);
});
