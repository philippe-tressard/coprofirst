/*
 *  **Le badge du titre « Destinataires » dit ce que la rangée coche** (03/10/2026,
 *  signalé à l'écran). Dans la Suite d'une affaire dont le défaut est « Résident
 *  concerné » (Nuisance, Sinistre…), la pastille cochée était bien celle-là, mais
 *  le badge du titre disait « Tous » : la Suite n'a pas de `lecture`, et la liste
 *  vide valait « Tous » pour le badge.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, deplierEtape, expect, simulerApi, test } from './aides';

const AFFAIRE = {
	id: 8,
	numero: 'TK-124291',
	titre: 'Bruit nocturne',
	description: 'Musique tard le soir.',
	categorie: 'nuisance',
	statut: 'en_cours',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	public_cible: null,
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	natures: ['activite'],
	cree_le: '2026-09-20T10:00:00',
	mis_a_jour_le: '2026-09-21T10:00:00',
};

const SUITE = {
	id: 32,
	ticket_id: 8,
	type: 'etat',
	contenu: '<p>Voisin prévenu.</p>',
	ancien_statut: 'ouvert',
	nouveau_statut: 'en_cours',
	statut_avant: 'ouvert',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	cree_le: '2026-09-21T10:00:00',
	fichiers_urls: [],
};

const section = (page: Page) =>
	page.locator('section.section-formulaire', {
		has: page.locator('.section-titre-texte', { hasText: 'Destinataires' }),
	});

test('Suite d’une Nuisance : la pastille « Résident concerné » et le badge du titre concordent', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets/8') return AFFAIRE;
		if (chemin === '/api/tickets/8/evolutions') return [SUITE];
	});
	await page.goto('/tickets/8');
	await attendreHydratation(page);
	await deplierEtape(page, 'La suite');
	await page.getByRole('button', { name: 'Modifier cette entrée' }).click();
	const destinataires = section(page);
	await expect(destinataires.locator('button', { hasText: /Résident concerné/ })).toHaveClass(
		/active/,
	);
	await expect(destinataires.getByRole('button', { name: 'Tous', exact: true })).not.toHaveClass(
		/active/,
	);
	await expect(destinataires.locator('.badge', { hasText: /^Tous$/ })).toHaveCount(0);
});
