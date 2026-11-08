/*
 *  **L'avis d'une question au règlement : synthèse courte, renvois, sections pliées**
 *  (08/11/2026, #2597).
 *
 *  Demandé : « la réponse est trop longue et confuse ; il faut justifier avec les §,
 *  une courte synthèse et des sections pliables du règlement et des AG ». Sur le VRAI
 *  écran, API simulée, ce que ces tests tiennent :
 *
 *  • repliée, la carte lit la synthèse SANS ses « [R1] » ;
 *  • dépliée, la synthèse se lit d'abord, puis « Ce qui fonde l'avis » — une ligne
 *    par renvoi, avec l'acte, la rubrique et la page — et trois sections PLIÉES ;
 *  • un clic sur un renvoi ouvre SA section, replie l'autre (un seul bloc ouvert à
 *    la fois) et amène à l'extrait, mot pour mot ;
 *  • un renvoi cité sans extrait derrière est signalé ;
 *  • un avis d'avant (sans renvois) se lit comme avant, section après section.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const CS = { ...MEMBRE_CS, id: 2, role: 'conseil_syndical', roles: ['conseil_syndical'] };
const ETAT = {
	disponible: true,
	texte_disponible: true,
	lien_reglement: null,
	categorie_id: null,
	categorie_ag_id: null,
	provenance: null,
};

const CITATION_R1 = 'Les parties communes ne peuvent recevoir aucune installation privative.';
const CITATION_R2 = 'Toute modification de façade est soumise à l’accord de l’assemblée générale.';
const CITATION_AG = 'L’assemblée autorise la pose de climatiseurs de teinte grise.';

const extrait = (surcharge: object) => ({
	citation: '',
	reference: '',
	apport: '',
	verifie: true,
	page: null,
	acte: null,
	source: 'reglement',
	rubrique: null,
	renvoi: null,
	...surcharge,
});

/** Un avis À RENVOIS, tel que le serveur le rend depuis le 08/11/2026. */
const AVIS = {
	id: 3,
	question: 'Puis-je installer une climatisation sur mon balcon ?',
	verdict: 'sous_conditions',
	verdict_libelle: 'Oui, sous conditions',
	verdict_ton: 'alerte',
	reponse:
		'<p>Oui, mais seulement après accord de l’assemblée [R2], qui l’a déjà donné pour un modèle gris [AG1]. Voir aussi [R9].</p>',
	reponse_sans_renvois:
		'<p>Oui, mais seulement après accord de l’assemblée, qui l’a déjà donné pour un modèle gris. Voir aussi.</p>',
	renvois_sans_extrait: ['R9'],
	selon_reglement: '<ul><li>La façade est une partie commune [R1][R2].</li></ul>',
	selon_ag: '<ul><li>L’AG du 12 juin 2025 a autorisé le modèle gris [AG1].</li></ul>',
	synthese: null,
	reserves: '<ul><li>Une autorisation donnée à un lot ne vaut pas pour les autres.</li></ul>',
	extraits: [
		extrait({
			citation: CITATION_R1,
			renvoi: 'R1',
			acte: 'LIVRE I',
			rubrique: 'CHAPITRE TROIS : PARTIES COMMUNES',
			page: 'RCP 1993 — PDF p. 45',
		}),
		extrait({
			citation: CITATION_R2,
			renvoi: 'R2',
			acte: 'LIVRE II',
			rubrique: 'MODIFICATIF › FAÇADES',
			page: 'MOD 1995 — PDF p. 3',
		}),
		extrait({
			citation: CITATION_AG,
			renvoi: 'AG1',
			source: 'ag',
			acte: 'Assemblée générale du 12 juin 2025',
			rubrique: 'Résolution n° 7 — Climatiseurs',
			page: 'PV — p. 3',
		}),
	],
	texte_id: 1,
	texte_en_vigueur: true,
	provenance: null,
	auteur_nom: 'Jean Dupont',
	modele: null,
	faq_item_id: null,
	peut_supprimer: false,
	cree_le: '2026-11-05T09:00:00',
};

/** Un avis d'AVANT : ni renvoi ni rubrique, la réponse longue et ses sections. */
const AVIS_ANCIEN = {
	...AVIS,
	id: 4,
	question: 'Puis-je fermer mon balcon ?',
	reponse: '<p>Oui, avec le modèle voté.</p>',
	reponse_sans_renvois: '<p>Oui, avec le modèle voté.</p>',
	renvois_sans_extrait: [],
	selon_reglement: '<p>Le modificatif exige une autorisation.</p>',
	selon_ag: null,
	reserves: null,
	extraits: [extrait({ citation: CITATION_R1, acte: 'LIVRE I', page: 'p. 12' })],
};

async function ouvrir(page: Page, questions: object[]) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return CS;
		if (chemin === '/api/reglement/acces') return { acces: true };
		if (chemin === '/api/reglement') return ETAT;
		if (chemin === '/api/reglement/questions') return questions;
	});
	await page.goto('/residence/reglement');
	await attendreHydratation(page);
}

const bandeau = (page: Page, titre: RegExp) => page.getByRole('button', { name: titre });

test('repliée, la carte lit la synthèse sans ses renvois', async ({ page }) => {
	await ouvrir(page, [AVIS]);
	const carte = page.locator('#question-reglement-3');
	await expect(
		carte.getByText(/qui l’a déjà donné pour un modèle gris\. Voir aussi\./),
	).toBeVisible();
	await expect(carte).not.toContainText('[R2]');
	await expect(carte).not.toContainText('[AG1]');
});

test('dépliée : la synthèse, ce qui fonde l’avis, puis trois sections pliées', async ({ page }) => {
	await ouvrir(page, [AVIS]);
	await page.getByText(AVIS.question).click();
	const carte = page.locator('#question-reglement-3');

	//  La synthèse garde ses renvois : ils renvoient à la liste dessous.
	await expect(carte.locator('.rich-content').first()).toContainText('[R2]');
	await expect(carte.getByRole('heading', { name: /Ce qui fonde l.avis/ })).toBeVisible();
	const renvoi = (code: string) => carte.getByRole('button', { name: new RegExp(`^${code}\\b`) });
	await expect(renvoi('R1')).toContainText('LIVRE I');
	await expect(renvoi('R1')).toContainText('CHAPITRE TROIS : PARTIES COMMUNES');
	await expect(renvoi('R1')).toContainText('RCP 1993 — PDF p. 45');
	await expect(renvoi('AG1')).toContainText('Résolution n° 7 — Climatiseurs');
	await expect(carte.getByText('Renvoi sans extrait')).toContainText('R9');

	//  Trois sections, toutes pliées : aucun extrait ne se lit encore.
	for (const titre of [/Le règlement de copropriété/, /Les assemblées générales/, /Réserves/]) {
		await expect(bandeau(page, titre)).toHaveAttribute('aria-expanded', 'false');
	}
	await expect(carte.getByText(CITATION_R1)).toHaveCount(0);
	await expect(carte.getByText(CITATION_AG)).toHaveCount(0);
});

test('un renvoi ouvre sa section, replie l’autre et amène à l’extrait mot pour mot', async ({
	page,
}) => {
	await ouvrir(page, [AVIS]);
	await page.getByText(AVIS.question).click();
	const carte = page.locator('#question-reglement-3');
	const reglement = bandeau(page, /Le règlement de copropriété/);
	const ag = bandeau(page, /Les assemblées générales/);

	await carte.getByRole('button', { name: /^AG1\b/ }).click();
	await expect(ag).toHaveAttribute('aria-expanded', 'true');
	await expect(reglement).toHaveAttribute('aria-expanded', 'false');
	await expect(carte.locator('#extrait-3-AG1')).toContainText(CITATION_AG);
	await expect(carte.locator('#extrait-3-AG1')).toBeInViewport();

	//  Un seul bloc ouvert à la fois : le règlement prend la place de l’AG.
	await carte.getByRole('button', { name: /^R2\b/ }).click();
	await expect(reglement).toHaveAttribute('aria-expanded', 'true');
	await expect(ag).toHaveAttribute('aria-expanded', 'false');
	await expect(carte.locator('#extrait-3-R2')).toContainText(CITATION_R2);
	await expect(carte.getByText(CITATION_AG)).toHaveCount(0);
	//  Le raisonnement en puces se lit au-dessus de ses extraits.
	await expect(carte.getByText('La façade est une partie commune')).toBeVisible();
});

test('un avis d’avant, sans renvois, se lit comme avant', async ({ page }) => {
	await ouvrir(page, [AVIS_ANCIEN]);
	await page.getByText(AVIS_ANCIEN.question).click();
	const carte = page.locator('#question-reglement-4');
	await expect(carte.getByRole('heading', { name: /D.après le règlement/ })).toBeVisible();
	await expect(carte.getByText(CITATION_R1)).toBeVisible();
	await expect(carte.getByRole('heading', { name: /Ce qui fonde l.avis/ })).toHaveCount(0);
	await expect(bandeau(page, /Le règlement de copropriété/)).toHaveCount(0);
});
