/*
 *  **Une affaire dépliée au fil : la brique des trois étapes, ouverte sur « La suite »**
 *  (arbitrage n° 66, 18/10/2026, #2078).
 *
 *  Le fil montrait trois encarts A (« Dernière mise à jour », « Synthèse », « Demande
 *  initiale » pliée), la liste Affaires la brique G (`RubriqueEtape`) : une même
 *  affaire, deux rendus. Décidé : la brique G partout, et le fil l'ouvre sur « La
 *  suite » — il répond à « quoi de neuf ». Seule l'étape dépliée change.
 *
 *  Ce que le test tient :
 *   1. le fil rend trois étapes, la suite ouverte, chacune avec SES pièces (garantie de
 *      la maquette A, TK-109008 : les photos de la clôture ne passent plus pour celles
 *      de la demande) ;
 *   2. une affaire sans suite n'a que sa demande, dépliée ;
 *   3. PARITÉ : la MÊME affaire, lue au fil et dans la liste, a les mêmes étapes — titres,
 *      ordre, teintes, résumés des étapes pliées. L'ouverture par défaut est la seule
 *      différence.
 *
 *  Le serveur est tenu par `test_flux_affaire_rubriques.py`.
 */
import type { Locator, Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';
import { AFFAIRE, ETAT_SYNTHESE, FIL } from './affaire-close-donnees';

const LIGNE = {
	numero: 'TK-142',
	categorie: 'panne',
	statut: 'résolu',
	priorite: 'normale',
	debut: null,
	perimetre_cible: [],
	public_cible: null,
	reserve_perimetre: false,
	confidentiel: false,
	epingle: false,
	assiste_ia: false,
};

//  La demande porte SA photo ; la clôture (l'entrée 5) les siennes.
const AFFAIRE_PIECES = { ...AFFAIRE, photos_urls: ['/uploads/demande.jpg'] };
const FIL_PIECES = FIL.map((e) =>
	e.id === 5 ? { ...e, fichiers_urls: ['/uploads/cloture-1.jpg', '/uploads/cloture-2.jpg'] } : e,
);

const CARTE_FIL = {
	id: 'tk_42',
	type: 'ticket_resolu',
	date: '2026-10-21T10:00:00',
	cree_le: AFFAIRE.cree_le,
	titre: AFFAIRE.titre,
	detail: 'Résolu en 08j',
	badges: ['#TK-142', 'Panne'],
	icon: '✅',
	meta: {
		ticket_id: 42,
		perimetre_codes: [],
		auteur: 'CS Témoin',
		affaire: LIGNE,
		statut: 'résolu',
		description: 'Une tache s’étend au plafond du hall.',
		demande: { le: AFFAIRE.cree_le, photos_urls: ['/uploads/demande.jpg'], fichiers_urls: [] },
		evol_contenu: 'Raccord remplacé.',
		evol_auteur: 'CS Témoin',
		evol_pieces: { photos_urls: [], fichiers_urls: [] },
		synthese: { texte: 'Raccord de la colonne remplacé.', validee: true },
	},
};

//  Une affaire neuve : pas de suite, pas de synthèse.
const NEUVE = {
	...AFFAIRE,
	id: 43,
	numero: 'TK-143',
	titre: 'Fuite au local vélos',
	description: 'Une flaque sous le robinet du local vélos.',
	statut: 'ouvert',
};
const CARTE_NEUVE = {
	...CARTE_FIL,
	id: 'tk_43',
	type: 'ticket_ouvert',
	titre: NEUVE.titre,
	icon: '🎫',
	meta: {
		ticket_id: 43,
		perimetre_codes: [],
		auteur: 'CS Témoin',
		affaire: { ...LIGNE, numero: 'TK-143', statut: 'ouvert' },
		statut: 'ouvert',
		description: 'Une flaque sous le robinet du local vélos.',
		demande: { le: NEUVE.cree_le, photos_urls: [], fichiers_urls: [] },
	},
};

//  Une photo de test servie sous chaque adresse `/uploads/…`.
const PHOTO = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="400" height="300" fill="#b9c6d6"/></svg>`;

async function simuler(page: Page) {
	await page.route('**/uploads/**', (route) =>
		route.fulfill({ contentType: 'image/svg+xml', body: PHOTO }),
	);
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/flux') return { items: [CARTE_FIL, CARTE_NEUVE], sante: {} };
		if (chemin === '/api/tickets') return [AFFAIRE_PIECES];
		if (chemin === '/api/tickets/42') return AFFAIRE_PIECES;
		if (chemin === '/api/tickets/42/evolutions') return FIL_PIECES;
		if (chemin === '/api/tickets/42/synthese') return ETAT_SYNTHESE;
		if (chemin === '/api/tickets/43') return NEUVE;
		if (chemin === '/api/tickets/43/evolutions') return [];
	});
}

async function deplierAuFil(page: Page, titre: string) {
	const carte = page.locator('.flux-groupes .carte-liste', { hasText: titre });
	await carte.click();
	await expect(carte.locator('.flux-body')).toBeVisible();
	return carte;
}

type Etape = { titre: string; ton: string; ouverte: boolean; resume: string | null };

/**  Les étapes d'une carte dépliée, telles qu'on les LIT : titre, teinte, ouverture, résumé. */
const etapes = (carte: Locator) =>
	carte.locator('.encart').evaluateAll((els): Etape[] =>
		els.map((e) => ({
			titre: (e.querySelector('.encart-titre')?.textContent ?? '').replace(/\s+/g, ' ').trim(),
			ton: [...e.classList].find((c) => c.startsWith('ton-')) ?? '',
			ouverte: e.querySelector('.encart-tete')?.getAttribute('aria-expanded') === 'true',
			resume: e.querySelector('.encart-resume')?.textContent?.trim() ?? null,
		})),
	);

test('une affaire résolue rend ses trois étapes, la suite ouverte, chacune avec ses pièces', async ({
	page,
}) => {
	await simuler(page);
	await page.goto('/tableau-de-bord');
	const carte = await deplierAuFil(page, AFFAIRE.titre);
	const corps = carte.locator('.flux-body');

	await expect(corps.locator('.encart-titre')).toHaveText([
		/^La demande$/,
		/^La suite\s*5 entrées$/,
		/^La synthèse$/,
	]);
	//  Le fil s'ouvre sur ce qui vient d'arriver ; la demande et la synthèse sont pliées
	//  sur une ligne qui dit l'essentiel.
	const tete = (titre: string) => corps.locator('.encart-tete', { hasText: titre });
	await expect(tete('La suite')).toHaveAttribute('aria-expanded', 'true');
	await expect(tete('La demande')).toHaveAttribute('aria-expanded', 'false');
	await expect(tete('La synthèse')).toHaveAttribute('aria-expanded', 'false');
	await expect(tete('La synthèse')).toContainText('Validée le 22 oct. 2026 · affaire close en 8 j');

	//  La suite : trois entrées, puis « plus anciennes ». La clôture porte SES photos…
	await expect(corps.locator('.evol-item')).toHaveCount(3);
	await expect(
		corps.getByRole('button', { name: /Voir les 2 entrées plus anciennes/ }),
	).toBeVisible();
	await expect(corps.locator('.evol-item').first()).toContainText('Résolu');
	await expect(corps.locator('.evol-item').first().locator('img')).toHaveCount(2);
	//  …la demande la sienne, cachée tant qu'elle est pliée — jamais sous la mise à jour.
	await expect(corps.locator('.evol-item').nth(1).locator('img')).toHaveCount(0);
	await expect(corps.locator('img[src*="demande.jpg"]')).toBeHidden();
	//  La capture de la carte telle qu'on l'ouvre — la preuve à montrer.
	await carte.screenshot({
		path: test.info().outputPath('carte-depliee.png'),
		animations: 'disabled',
	});

	//  Une seule étape à la fois : ouvrir la demande replie la suite.
	await tete('La demande').click();
	await expect(tete('La demande')).toHaveAttribute('aria-expanded', 'true');
	await expect(tete('La suite')).toHaveAttribute('aria-expanded', 'false');
	await expect(corps.locator('img[src*="demande.jpg"]')).toBeVisible();
	await expect(corps).toContainText('Une tache s’étend au plafond du hall.');

	//  L'état est déjà dans la ligne de pastilles : il ne se redit pas dessous.
	await expect(corps).not.toContainText('État :');
});

test('une affaire sans suite rend sa demande dépliée, seule', async ({ page }) => {
	await simuler(page);
	await page.goto('/tableau-de-bord');
	const carte = await deplierAuFil(page, NEUVE.titre);
	const corps = carte.locator('.flux-body');
	await expect(corps.locator('.encart-titre')).toHaveText([/^La demande$/]);
	await expect(corps.locator('.encart-tete')).toHaveAttribute('aria-expanded', 'true');
	await expect(corps).toContainText('Une flaque sous le robinet du local vélos');
	await expect(corps.locator('.encart-tete', { hasText: 'La suite' })).toHaveCount(0);
});

test('PARITÉ : la même affaire a les mêmes étapes au fil et dans la liste', async ({ page }) => {
	await simuler(page);

	await page.goto('/tableau-de-bord');
	const auFil = await deplierAuFil(page, AFFAIRE.titre);
	await expect(auFil.locator('.encart')).toHaveCount(3);
	const fil = await etapes(auFil);

	await page.goto('/tickets');
	await attendreHydratation(page);
	const carte = page.locator('.carte-liste', { hasText: AFFAIRE.titre });
	await carte.getByText(AFFAIRE.titre).click();
	await expect(carte.locator('.encart')).toHaveCount(3);
	const liste = await etapes(carte);

	//  Mêmes titres, même ordre, mêmes teintes : un seul composant.
	expect(fil.map(({ titre, ton }) => ({ titre, ton }))).toEqual(
		liste.map(({ titre, ton }) => ({ titre, ton })),
	);
	expect(fil.map((e) => e.ton)).toEqual(['ton-neutre', 'ton-info', 'ton-succes']);
	//  Les mêmes résumés, là où l'étape est pliée des deux côtés.
	for (const [i, e] of fil.entries()) {
		if (!e.ouverte && !liste[i].ouverte) expect(e.resume, e.titre).toBe(liste[i].resume);
	}
	expect(fil[2].resume, 'la synthèse pliée dit son état').toContain('Validée le');
	//  La SEULE différence : l'étape dépliée par défaut.
	expect(fil.map((e) => e.ouverte)).toEqual([false, true, false]);
	expect(liste.map((e) => e.ouverte)).toEqual([true, false, false]);
});
