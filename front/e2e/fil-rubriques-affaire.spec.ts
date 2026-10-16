/*
 *  **Une affaire dépliée au fil : trois rubriques, chacune avec SES pièces.**
 *
 *  Signalé à l'écran le 15/10/2026 (TK-109008) : la carte d'une affaire résolue
 *  montrait le texte de la DEMANDE et, dessous, les photos de la CLÔTURE —
 *  rien ne disait d'où elles venaient. Arbitré parmi cinq maquettes (A) :
 *  « Dernière mise à jour » (texte, auteur, ses pièces), « Synthèse » si le
 *  serveur l'envoie, « Demande initiale » pliée avec les siennes.
 *
 *  Le serveur est tenu par `test_flux_affaire_rubriques.py` ; ce test-ci tient
 *  ce qu'on LIT, avec les clés que le serveur envoie.
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';

const LIGNE = {
	numero: 'TK-109008',
	categorie: 'panne',
	statut: 'résolu',
	priorite: 'haute',
	debut: null,
	perimetre_cible: [],
	public_cible: null,
	reserve_perimetre: false,
	confidentiel: false,
	epingle: false,
	assiste_ia: false,
};
const RESOLUE = {
	id: 'tk_7',
	type: 'ticket_resolu',
	date: '2026-10-15T18:15:00',
	cree_le: '2026-10-13T19:00:00',
	titre: 'Portillon en panne et fermé',
	detail: 'Résolu en 02j00h15',
	badges: ['#TK-109008', 'Panne', 'urgent'],
	icon: '✅',
	meta: {
		ticket_id: 7,
		perimetre_codes: [],
		auteur: 'Claire MARTIN',
		affaire: LIGNE,
		statut: 'résolu',
		description: 'Le portillon ne s’ouvre plus après 21 h, un bruit de moteur à vide.',
		demande: {
			le: '2026-10-13T19:00:00',
			photos_urls: ['/uploads/demande.jpg'],
			fichiers_urls: [],
		},
		photos_urls: ['/uploads/cloture-1.jpg', '/uploads/cloture-2.jpg'],
		fichiers_urls: [],
		evol_contenu: 'Gâche remplacée, portillon de nouveau fonctionnel.',
		evol_auteur: 'Paul DURAND',
		evol_pieces: {
			photos_urls: ['/uploads/cloture-1.jpg', '/uploads/cloture-2.jpg'],
			fichiers_urls: [],
		},
		synthese: { texte: 'Motoréducteur bloqué, gâche remplacée de nuit.', validee: true },
	},
};
const OUVERTE = {
	id: 'tk_8',
	type: 'ticket_ouvert',
	date: '2026-10-15T17:00:00',
	cree_le: '2026-10-15T17:00:00',
	titre: 'Fuite au local vélos',
	detail: 'Nouveau ticket',
	badges: ['#TK-200001', 'Panne'],
	icon: '🎫',
	meta: {
		ticket_id: 8,
		perimetre_codes: [],
		auteur: 'Claire MARTIN',
		affaire: { ...LIGNE, numero: 'TK-200001', statut: 'ouvert', priorite: 'normale' },
		statut: 'ouvert',
		description: 'Une flaque sous le robinet du local vélos.',
		demande: {
			le: '2026-10-15T17:00:00',
			photos_urls: ['/uploads/fuite.jpg'],
			fichiers_urls: [],
		},
		photos_urls: ['/uploads/fuite.jpg'],
		fichiers_urls: [],
	},
};

//  Une photo de test servie sous chaque adresse `/uploads/…` : une image cassée
//  aurait la même place dans la page, pas la même allure à la capture.
const PHOTO = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="400" height="300" fill="#b9c6d6"/></svg>`;

async function simuler(page: Page) {
	await page.route('**/uploads/**', (route) =>
		route.fulfill({ contentType: 'image/svg+xml', body: PHOTO }),
	);
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/flux') return { items: [RESOLUE, OUVERTE], sante: {} };
	});
}

async function deplier(page: Page, titre: string) {
	const carte = page.locator('.flux-groupes .carte-liste', { hasText: titre });
	await carte.click();
	await expect(carte.locator('.flux-body')).toBeVisible();
	return carte;
}

test('une affaire résolue rend ses trois rubriques, chacune avec ses pièces', async ({ page }) => {
	await simuler(page);
	await page.goto('/tableau-de-bord');
	const carte = await deplier(page, 'Portillon en panne et fermé');

	const suite = carte.getByRole('region', { name: 'Dernière mise à jour' });
	await expect(suite).toContainText('Gâche remplacée, portillon de nouveau fonctionnel.');
	await expect(suite).toContainText('Paul DURAND');
	await expect(suite.locator('img')).toHaveCount(2);

	const synthese = carte.getByRole('region', { name: 'Synthèse' });
	await expect(synthese).toContainText('Motoréducteur bloqué');
	await expect(synthese).toContainText('validée par le conseil');

	//  La demande : pliée, sa photo dedans — jamais sous la mise à jour.
	const demande = carte.locator('details.rubrique-demande');
	await expect(demande).not.toHaveAttribute('open', '');
	await expect(demande.locator('summary')).toContainText('Demande initiale');
	await expect(demande.locator('img')).toBeHidden();
	//  La capture de la carte telle qu'on l'ouvre — la preuve à montrer.
	await carte.screenshot({
		path: test.info().outputPath('carte-depliee.png'),
		animations: 'disabled',
	});
	await demande.locator('summary').click();
	await expect(demande.locator('img')).toHaveCount(1);
	await expect(demande).toContainText('bruit de moteur à vide');

	//  L'état est déjà dans la ligne de pastilles : il ne se redit pas dessous.
	await expect(carte.locator('.flux-body')).not.toContainText('État :');
});

test('une affaire sans suite rend sa demande dépliée, sans rubrique', async ({ page }) => {
	await simuler(page);
	await page.goto('/tableau-de-bord');
	const carte = await deplier(page, 'Fuite au local vélos');
	await expect(carte.locator('.flux-body')).toContainText('Une flaque sous le robinet');
	await expect(carte.locator('.flux-body img')).toHaveCount(1);
	await expect(carte.locator('details.rubrique-demande')).toHaveCount(0);
	await expect(carte.getByRole('region', { name: 'Dernière mise à jour' })).toHaveCount(0);
});
