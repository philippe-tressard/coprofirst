/**
 *  **Au fil, une affaire datée dit QUAND elle a lieu, dans sa gouttière**
 *  (maquette C « Échéance », choisie parmi cinq le 10/11/2026).
 *
 *  La colonne se lit de haut en bas : l'heure de la nouvelle, le classement
 *  (« CAL. »), puis la vignette — le délai SERVI par l'API (`meta.affaire.echeance`,
 *  jamais compté à l'écran), et la ou les dates.
 *
 *  Ce que rien d'autre ne verrait :
 *    • l'ordre des trois étages, que le créneau de `Gouttiere` décide ;
 *    • une date plus LARGE que la colonne, avec la police réellement appliquée
 *      (`standards/04` §14) — « mar. 17 nov. » dans cinq rem ;
 *    • une affaire close qui garderait son compte à rebours ;
 *    • une affaire SANS date qui gagnerait un étage vide.
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal } from './defilement';

const REDACTEUR = 'Jean-Hervé KERBRAT';
const LIGNE = {
	numero: 'TK-787609',
	categorie: 'entretien',
	categorie_libelle: 'Entretien',
	statut: 'chez_prestataire',
	close: false,
	priorite: 'normale',
	urgente: false,
	perimetre_cible: [],
	public_cible: null,
	reserve_perimetre: false,
	confidentiel: false,
	epingle: false,
	assiste_ia: false,
};
const carte = (id: number, titre: string, affaire: Record<string, unknown>) => ({
	id: `tk_${id}`,
	type: 'ticket_ouvert',
	date: '2026-11-09T15:19:00Z',
	titre,
	detail: 'Mise à jour',
	badges: [`#${LIGNE.numero}`, 'Entretien'],
	icon: '🛠️',
	meta: {
		ticket_id: id,
		perimetre_codes: [],
		auteur: REDACTEUR,
		affaire: { ...LIGNE, ...affaire },
	},
});
const FLUX = {
	items: [
		carte(1, 'Vérification incendie', {
			natures: ['calendrier'],
			debut: '2026-11-17T08:00:00Z',
			fin: null,
			echeance: { etat: 'a_venir', jours: 8, libelle: 'J-8', plusieurs_jours: false },
		}),
		carte(2, 'Ravalement de la façade', {
			natures: ['calendrier'],
			debut: '2026-11-17T08:00:00Z',
			fin: '2026-11-19T16:00:00Z',
			echeance: { etat: 'a_venir', jours: 8, libelle: 'J-8', plusieurs_jours: true },
		}),
		carte(3, 'Visite annulée', {
			natures: ['calendrier'],
			statut: 'annulé',
			close: true,
			debut: '2026-11-17T08:00:00Z',
			fin: null,
			echeance: { etat: 'close', jours: 8, libelle: null, plusieurs_jours: false },
		}),
		carte(4, 'Porte du hall', { natures: ['activite'], debut: null, fin: null, echeance: null }),
	],
	sante: {},
};

const ouvrir = async (page: Page) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/flux') return FLUX;
	});
	await page.goto('/tableau-de-bord');
	await expect(page.locator('.flux-groupes .carte-liste')).toHaveCount(4);
};
const gouttiere = (page: Page, titre: string) =>
	page.locator('.flux-groupes .carte-liste', { hasText: titre }).locator('.gouttiere');

test('le délai servi, puis la date, sous le classement', async ({ page }) => {
	await ouvrir(page);
	const g = gouttiere(page, 'Vérification incendie');
	await expect(g.locator('.e-delai')).toHaveText('J-8');
	await expect(g.locator('.e-dates')).toHaveText(/17 nov\./);
	await expect(g.locator('.e-dates time')).toHaveCount(1);

	//  L'ordre : quand on en a parlé · ce que c'est · quand ça se passe — de haut
	//  en bas dans la colonne, de gauche à droite sur la ligne du téléphone.
	const place = async (selecteur: string) => {
		const colonne = await g.boundingBox();
		const boite = await g.locator(selecteur).boundingBox();
		if (!colonne || !boite) return -1;
		return colonne.height > colonne.width ? boite.y : boite.x;
	};
	await expect
		.poll(async () => {
			const [date, nature, echeance] = [
				await place('.g-date'),
				await place('.g-nature'),
				await place('.echeance'),
			];
			return date >= 0 && date < nature && nature < echeance;
		})
		.toBe(true);
});

test('une plage montre ses deux dates, une affaire close perd son délai', async ({ page }) => {
	await ouvrir(page);
	const plage = gouttiere(page, 'Ravalement de la façade');
	await expect(plage.locator('.e-dates')).toHaveText(/17 nov\..*→\s19 nov\./);

	const close = gouttiere(page, 'Visite annulée');
	await expect(close.locator('.e-dates')).toHaveText(/17 nov\./);
	await expect(close.locator('.e-delai')).toHaveCount(0);

	//  Sans date, pas d'étage de plus : ce que l'objet n'a pas ne s'invente pas.
	const sansDate = gouttiere(page, 'Porte du hall');
	await expect(sansDate.locator('.g-nature')).toBeVisible();
	await expect(sansDate.locator('.echeance')).toHaveCount(0);
});

test('la vignette tient dans la colonne, et la page ne défile pas en largeur', async ({ page }) => {
	await ouvrir(page);
	for (const titre of ['Vérification incendie', 'Ravalement de la façade']) {
		const g = gouttiere(page, titre);
		await expect(g.locator('.echeance')).toBeVisible();
		await expect
			.poll(() => g.evaluate((el) => el.scrollWidth - el.clientWidth), {
				message: `la vignette de « ${titre} » dépasse de sa gouttière`,
			})
			.toBeLessThanOrEqual(1);
	}
	await attendreSansDefilementHorizontal(page);
});
