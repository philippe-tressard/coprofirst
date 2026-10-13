/*
 *  **Le fil d'une actualité de la liste se charge au geste** (13/10/2026, #1861).
 *
 *  Le reste de #1860 : `ActualiteEnListe`, rendue dans la MÊME liste que les
 *  affaires, importait le fil (`RubriqueHistorique`) et le panneau d'options —
 *  l'ouverture d'Affaires les téléchargeait (140 → 126 Ko gz une fois retirés).
 *  `lint:poids-ouverture` tient le build ; ce test tient ce que seul un écran
 *  montre : l'ouverture ne demande pas le fil, le survol le précharge, et le
 *  dépliage l'affiche — rien n'est perdu en route.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const ACTUALITE = {
	id: 9,
	numero: 'TK-124309',
	titre: 'Coupure d’eau jeudi matin',
	description: 'Intervention sur la colonne montante.',
	categorie: 'actualite',
	statut: 'ouvert',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	natures: ['activite'],
	cree_le: '2026-09-20T10:00:00',
	mis_a_jour_le: '2026-09-20T10:00:00',
};

const SUITE = {
	id: 31,
	ticket_id: 9,
	type: 'commentaire',
	contenu: '<p>Le plombier confirme 8 h – 11 h.</p>',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	cree_le: '2026-09-21T09:00:00',
};

const estLeFil = (chemin: string) => chemin.endsWith('/FilActualiteEnListe.svelte');

async function ouvrirAffaires(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [ACTUALITE];
		if (chemin === '/api/tickets/9') return ACTUALITE;
		if (chemin === '/api/tickets/9/evolutions') return [SUITE];
	});
}

test('l’ouverture ne télécharge pas le fil ; le survol le précharge ; le dépliage l’affiche', async ({
	page,
}) => {
	await ouvrirAffaires(page);
	const demandes: string[] = [];
	page.on('request', (r) => {
		if (estLeFil(new URL(r.url()).pathname)) demandes.push(r.url());
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	const titre = page.locator('.carte-liste').first().getByText(ACTUALITE.titre);
	await expect(titre).toBeVisible();
	expect(demandes, 'le fil est demandé dès l’ouverture').toHaveLength(0);

	await titre.hover();
	await expect.poll(() => demandes.length, 'le survol ne précharge pas le fil').toBe(1);

	await titre.click();
	const corps = page.locator('.carte-liste .carte-corps');
	await expect(corps).toContainText(ACTUALITE.description);
	await expect(corps).toContainText('Le plombier confirme');
});
