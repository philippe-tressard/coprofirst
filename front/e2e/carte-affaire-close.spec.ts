/*
 *  **La carte d'une affaire close, dépliée — maquette A** (arbitrée le 15/10/2026).
 *
 *  Repliée, la carte dit qu'une synthèse validée l'accompagne (🧾 Synthèse).
 *  Dépliée, elle se lit en trois rubriques titrées, dans cet ordre : la DEMANDE,
 *  la SYNTHÈSE (texte d'abord, puis les chiffres ; la chronologie pliée), la
 *  SUITE — trois entrées, les plus anciennes repliées, et la Suite de synthèse
 *  n'y figure plus : elle a son bloc. Chaque entrée porte crayon et corbeille au
 *  trait, et la corbeille demande confirmation avant d'effacer.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const AFFAIRE = {
	id: 42,
	numero: 'TK-142',
	titre: 'Fuite d’eau au plafond du hall B',
	description: '<p>Une tache s’étend au plafond du hall.</p>',
	categorie: 'panne',
	statut: 'résolu',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	synthese_validee: true,
	natures: ['activite'],
	cree_le: '2026-10-12T09:00:00',
	mis_a_jour_le: '2026-10-21T09:00:00',
};

const entree = (id: number, jour: number, extra: Record<string, unknown>) => ({
	id,
	ticket_id: 42,
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	cree_le: `2026-10-${String(jour).padStart(2, '0')}T10:00:00`,
	fichiers_urls: [],
	...extra,
});

const FIL = [
	entree(1, 12, { type: 'commentaire', contenu: '<p>Signalée au gardien.</p>' }),
	entree(2, 13, { type: 'etat', ancien_statut: 'ouvert', nouveau_statut: 'en_cours' }),
	entree(3, 14, { type: 'commentaire', contenu: '<p>Le plombier passe jeudi.</p>' }),
	entree(4, 20, { type: 'commentaire', contenu: '<p>Raccord remplacé.</p>' }),
	entree(5, 21, { type: 'etat', ancien_statut: 'en_cours', nouveau_statut: 'résolu' }),
	entree(6, 21, { type: 'synthese' }),
];

const METRIQUES = {
	version: 1,
	issue: 'résolu',
	ouverte_le: '2026-10-12T09:00:00',
	close_le: '2026-10-21T10:00:00',
	duree_totale: 8,
	premiere_reponse_syndic: 1,
	relances: 0,
	suites: 5,
	etapes: [{ statut: 'en_cours', jours: 6 }],
	etape_plus_longue: 'en_cours',
	reaction_relance: null,
	semaines: [2, 2, 1],
	semaines_muettes: 0,
	chronologie: [],
	reouvertures: 0,
	comparaison: null,
};

const ETAT_SYNTHESE = {
	produisible: false,
	en_attente: false,
	synthese: {
		id: 1,
		ticket_id: 42,
		evolution_id: 6,
		statut: 'validee',
		metriques: METRIQUES,
		synthese: '<p>Raccord de la colonne remplacé.</p>',
		difficultes: '<p>La clé de la gaine manquait.</p>',
		amelioration: null,
		prompt_complement: null,
		assiste_ia: false,
		motif_vide: null,
		produite_le: '2026-10-21T10:30:00',
		validee_le: '2026-10-22T11:00:00',
		validee_par_nom: 'CS Témoin',
	},
};

async function ouvrir(page: Page, moi = MEMBRE_CS) {
	const effacees: string[] = [];
	page.on('request', (r) => {
		if (r.method() === 'DELETE') effacees.push(new URL(r.url()).pathname);
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return moi;
		if (chemin === '/api/tickets') return [AFFAIRE];
		if (chemin === '/api/tickets/42') return AFFAIRE;
		if (chemin === '/api/tickets/42/evolutions') return FIL;
		if (chemin === '/api/tickets/42/synthese') return ETAT_SYNTHESE;
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	return effacees;
}

test('repliée, la carte dit la synthèse ; dépliée, trois rubriques dans l’ordre', async ({
	page,
}) => {
	await ouvrir(page);
	const carte = page.locator('.carte-liste').first();
	await expect(carte).toContainText('🧾 Synthèse');

	await carte.getByText(AFFAIRE.titre).click();
	const corps = carte.locator('.carte-corps');
	await expect(corps.locator('.intertitre')).toHaveText([
		'La demande',
		'🧾 La synthèse',
		'La suite · 5',
	]);
	//  Le texte de la synthèse se lit AVANT ses chiffres.
	await expect
		.poll(async () => {
			const texte = await corps.innerText();
			return texte.indexOf('Raccord de la colonne remplacé') < texte.indexOf('Les chiffres');
		})
		.toBe(true);
	//  La chronologie est pliée.
	await expect(corps.locator('details.plies')).not.toHaveAttribute('open', '');
	//  Trois entrées, puis les plus anciennes — la Suite de synthèse n'y est pas.
	await expect(corps.locator('.evol-item')).toHaveCount(3);
	await expect(
		corps.getByRole('button', { name: /Voir les 2 entrées plus anciennes/ }),
	).toBeVisible();
	await expect(corps).toContainText('Résolu le 21 oct.');
});

test('la corbeille d’une entrée demande confirmation avant d’effacer', async ({ page }) => {
	const effacees = await ouvrir(page, ADMIN);
	const carte = page.locator('.carte-liste').first();
	await carte.getByText(AFFAIRE.titre).click();

	const premiere = carte.locator('.evol-item').first();
	await expect(premiere.getByRole('button', { name: 'Modifier cette entrée' })).toBeVisible();
	await premiere.getByRole('button', { name: 'Supprimer cette entrée' }).click();

	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('L’état de l’affaire ne change pas');
	await boite.getByRole('button', { name: 'Annuler' }).click();
	expect(effacees, 'Annuler n’efface rien').toHaveLength(0);

	await premiere.getByRole('button', { name: 'Supprimer cette entrée' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Supprimer' }).click();
	await expect.poll(() => effacees).toEqual(['/api/tickets/42/evolutions/5']);
});
