/*
 *  **Corriger une actualité en « Étude & travaux » s'enregistre** (29/09/2026).
 *
 *  Signalé en production (v2.83.1) sur TK-A00017 : ✏️ Modifier une actualité,
 *  catégorie « Étude & travaux », Enregistrer → « Une actualité n'a pas d'état
 *  de suivi : c'est sa catégorie qui en décide » (422).
 *
 *  L'écran envoie, pour toute affaire suivie, son état — « Ouvert » pour une
 *  actualité qui en devient une (`chargeUtileAffaire`) ; le serveur jugeait la
 *  catégorie d'AVANT la correction. La règle du serveur est tenue par
 *  `api/tests/test_categorie_actualite.py`
 *  (`test_l_ecran_corrige_une_actualite_en_etude_avec_son_etat`), sur CE corps.
 *  Ce test-ci tient l'autre moitié du contrat : ce que l'écran envoie vraiment,
 *  et qu'il dit « modifiée » sans message d'erreur.
 */
import { attendreHydratation, choisirPastille, expect, simulerApi, test } from './aides';
import { lectureServie } from './apercus-lecture';

const ACTUALITE = {
	id: 50,
	numero: 'TK-A00017',
	titre: 'Réfection de la cage d’escalier',
	description: 'Le projet est à l’étude.',
	categorie: 'actualite',
	statut: 'publie',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	public_cible: [],
	//  Qui la lit, SERVI avec elle (#2633) : la correction compare cette pastille à
	//  celle de la saisie pour annoncer le changement de lecteurs.
	lecture: lectureServie({
		categorie: 'actualite',
		statut: 'publie',
		public_cible: [],
		perimetre_cible: ['résidence'],
	}),
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	natures: ['actualite'],
	cree_le: '2026-09-20T10:00:00',
	mis_a_jour_le: '2026-09-20T10:00:00',
};

test('une actualité corrigée en Étude & travaux part « Ouvert », et s’enregistre', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [ACTUALITE];
		if (chemin === '/api/tickets/50') return ACTUALITE;
	});
	let corps: Record<string, unknown> | null = null;
	//  Enregistrée APRÈS : Playwright essaie la dernière route d'abord.
	await page.route(
		(url) => url.pathname === '/api/tickets/50',
		(route) => {
			if (route.request().method() !== 'PATCH') return route.fallback();
			corps = route.request().postDataJSON();
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({ ...ACTUALITE, categorie: 'etude_travaux', statut: 'ouvert' }),
			});
		},
	);
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: 'Modifier', exact: true }).first().click();
	await choisirPastille(page, /Étude & travaux/);
	await page.getByRole('button', { name: 'Enregistrer', exact: true }).first().click();
	//  Changer de nature se confirme (`alerteCorrection`).
	await page.getByRole('dialog').getByRole('button', { name: 'Enregistrer' }).click();

	await expect.poll(() => corps).not.toBeNull();
	expect(corps).toMatchObject({ categorie: 'etude_travaux', statut: 'ouvert' });
	await expect(page.getByText(/modifiée/)).toBeVisible();
	await expect(page.getByText(/n’a pas d’état de suivi|n'a pas d'état de suivi/)).toHaveCount(0);
});
