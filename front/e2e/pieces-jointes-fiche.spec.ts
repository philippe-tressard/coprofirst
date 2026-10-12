/*
 *  **Les pièces jointes d'une fiche de Ma résidence : UNE liste, l'objet
 *  standard, dix fichiers en tout** (11/10/2026).
 *
 *  La première version montrait deux blocs à l'édition d'un plan : le fichier
 *  du document (1/1), puis « Annexes — jusqu'à dix ». Signalé : *« ne pas mettre
 *  Annexes — utilise l'objet PJ standard une seule fois en principal ; on pourra
 *  joindre jusqu'à 10 fichiers »*, puis *« ne réinvente pas cet objet, il doit
 *  être standard »*.
 *
 *  Ce test tient ce que l'écran montre et ce qui part : un seul sélecteur, le
 *  fichier du plan en première pastille, le compteur sur dix ; et la croix de
 *  cette pastille demande au serveur de faire monter la suivante à sa place.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const PLAN = {
	id: 1,
	titre: 'Plan de masse',
	description: '',
	fichier_nom: 'plan.pdf',
	taille_octets: 100,
	mime_type: 'application/pdf',
	categorie_id: 11,
	contrat_id: null,
	ticket_id: null,
	evenement_id: null,
	document_parent_id: null,
	diagnostic_rapport_id: null,
	regle_residence_id: null,
	perimetre: 'résidence',
	batiment_id: null,
	publie_le: '2026-10-01T10:00:00',
	annee: null,
	date_ag: null,
	batiments_ids_json: null,
	perimetre_cible: [],
};
const ANNEXE = {
	...PLAN,
	id: 2,
	titre: 'Légende.pdf',
	fichier_nom: 'legende.pdf',
	categorie_id: null,
	document_parent_id: 1,
};

async function editerLePlan(page: Page): Promise<string[]> {
	const retraits: string[] = [];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/documents/categories')
			return [{ id: 11, code: 'plan_residence', libelle: 'Plans' }];
		if (chemin === '/api/copropriete') return { id: 1, nom: 'Résidence témoin' };
	});
	await page.route(
		(url) => url.pathname === '/api/documents',
		(route) => {
			const parametres = new URL(route.request().url()).searchParams;
			const corps =
				parametres.get('categorie') === 'plan_residence'
					? [PLAN]
					: parametres.has('annexes_de') || parametres.get('document_parent_id') === '1'
						? [ANNEXE]
						: [];
			return route.fulfill({ status: 200, json: corps });
		},
	);
	await page.route(
		(url) => url.pathname === '/api/documents/1/fichier',
		(route) => {
			retraits.push(route.request().method());
			return route.fulfill({ status: 200, json: { ...PLAN, fichier_nom: 'legende.pdf' } });
		},
	);
	await page.goto('/residence');
	await attendreHydratation(page);
	const carte = page.locator('.carte-liste', { hasText: 'Plan de masse' });
	const modifier = carte.getByRole('button', { name: 'Modifier' });
	//  La carte rendue d'abord : `isVisible` jugerait l'instant (#1830).
	await expect(carte).toBeVisible();
	if (!(await modifier.isVisible())) await carte.getByText('Plan de masse').first().click();
	await modifier.click();
	return retraits;
}

test('un seul sélecteur : le fichier du plan en tête, puis les autres, sur dix', async ({
	page,
}) => {
	await editerLePlan(page);
	const formulaire = page.getByRole('group', { name: 'Modifier le document' });
	await expect(formulaire.getByText(/Annexes/)).toHaveCount(0);
	await expect(formulaire.getByText(/Pour le remplacer/)).toHaveCount(0);
	await expect(formulaire.locator('input[type=file]')).toHaveCount(1);
	await expect(formulaire.getByText(/2\/10/)).toBeVisible();
	const pastilles = formulaire.getByRole('button', { name: /^Retirer / });
	await expect(pastilles).toHaveCount(2);
	//  Le nom accessible tait l'extension : la pastille la porte en préfixe (« PDF: »).
	await expect(pastilles.first()).toHaveAccessibleName('Retirer plan');
	await expect(pastilles.nth(1)).toHaveAccessibleName('Retirer Légende');
});

test('retirer le fichier du plan demande au serveur de faire monter le suivant', async ({
	page,
}) => {
	const retraits = await editerLePlan(page);
	await page.getByRole('button', { name: 'Retirer plan', exact: true }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Supprimer' }).click();
	await expect.poll(() => retraits).toEqual(['DELETE']);
});
