/*
 *  **Ma résidence › Règlement — l'onglet ouvert aux copropriétaires (11/10/2026).**
 *
 *  Venu de l'Espace CS. Ce que ces tests tiennent, sur le VRAI écran, API simulée :
 *
 *  • un copropriétaire voit l'onglet quand l'administration le lui a ouvert, et
 *    seulement alors — fermé, l'onglet disparaît et son adresse ramène à la Fiche ;
 *  • il y lit une phrase et le lien vers le règlement publié, jamais les fichiers
 *    que l'assistant lit, et ses questions sans l'icône de publication en FAQ ;
 *  • l'administration, seule, voit ces fichiers dans l'objet Pièces jointes
 *    standard (11/10/2026) ;
 *  • le conseil syndical publie, et ne voit pas les fichiers non plus ;
 *  • l'ancienne adresse de l'Espace CS mène ici, ancre comprise.
 *
 *  Le serveur refuse de son côté (`api/tests/test_question_reglement.py`) : ces
 *  tests vérifient que l'écran ne PROPOSE pas ce que le serveur refuserait.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const COPROPRIETAIRE = {
	...MEMBRE_CS,
	id: 5,
	prenom: 'Jean',
	nom: 'Dupont',
	statut: 'copropriétaire_bailleur',
	role: 'propriétaire',
	roles: ['propriétaire'],
};

const ADMIN = { ...MEMBRE_CS, id: 2, role: 'admin', roles: ['admin'] };
const LIEN = '/residence#doc-27';

/** `EtatReglement` tel que le serveur le rend à qui n'est pas l'administration. */
const ETAT_LECTEUR = {
	disponible: true,
	texte_disponible: true,
	lien_reglement: LIEN,
	categorie_id: null,
};
/** …et à l'administration : la catégorie où joindre les fichiers, pas de lien. */
const ETAT_ADMIN = { ...ETAT_LECTEUR, lien_reglement: null, categorie_id: 40 };

/** Un fichier du règlement joint (`Document`, catégorie réservée à l'admin). */
const FICHIER = {
	id: 91,
	titre: 'RCP consolidé',
	description: '',
	fichier_nom: 'rcp.md',
	taille_octets: 203008,
	mime_type: 'text/markdown',
	categorie_id: 40,
	contrat_id: null,
	ticket_id: null,
	evenement_id: null,
	document_parent_id: null,
	diagnostic_rapport_id: null,
	regle_residence_id: null,
	perimetre: 'résidence',
	batiment_id: null,
	publie_le: '2026-10-11T10:00:00',
	annee: null,
};

/** `QuestionReglement` — sans modèle ni coût, comme pour un copropriétaire. */
const QUESTION = {
	id: 3,
	question: 'Puis-je installer une climatisation sur mon balcon ?',
	verdict: 'sous_conditions',
	verdict_libelle: 'Oui, sous conditions',
	reponse: '<p>Oui, après autorisation de l’assemblée.</p>',
	reserves: null,
	extraits: [],
	texte_id: 1,
	texte_en_vigueur: true,
	texte_charge_le: '2026-10-01T10:00:00',
	auteur_nom: 'Jean Dupont',
	modele: null,
	cout_usd: null,
	faq_item_id: null,
	cree_le: '2026-10-05T09:00:00',
};

async function ouvrir(
	page: Page,
	{ compte, acces, adresse }: { compte: object; acces: boolean; adresse: string },
) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return compte;
		if (chemin === '/api/reglement/acces') return { acces };
		if (chemin === '/api/reglement') return compte === ADMIN ? ETAT_ADMIN : ETAT_LECTEUR;
		if (chemin === '/api/documents') return [FICHIER];
		if (chemin === '/api/reglement/questions') return [QUESTION];
	});
	await page.goto(adresse);
	await attendreHydratation(page);
}

const ongletReglement = (page: Page) => page.locator('.tabs').getByText('Règlement');

test('ouvert, le copropriétaire lit le lien et ses questions — ni fichier ni geste du conseil', async ({
	page,
}) => {
	await ouvrir(page, { compte: COPROPRIETAIRE, acces: true, adresse: '/residence/reglement' });
	await expect(ongletReglement(page)).toBeVisible();
	await expect(
		page.getByRole('link', { name: 'consulter le règlement de copropriété' }),
	).toHaveAttribute('href', LIEN);
	await expect(page.getByText(/interrogez un juriste ou le syndic/)).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Vos questions' })).toBeVisible();
	await expect(page.getByText(QUESTION.question)).toBeVisible();
	//  Ce que le serveur lui refuserait, l'écran ne le propose pas.
	await expect(page.getByRole('button', { name: 'Publier dans la FAQ' })).toHaveCount(0);
	await expect(page.getByText(FICHIER.titre)).toHaveCount(0);
	await expect(page.getByText(/Section visible de l'administration/)).toHaveCount(0);
});

test('l’administration seule voit les fichiers, dans les pièces jointes standard', async ({
	page,
}) => {
	await ouvrir(page, { compte: ADMIN, acces: true, adresse: '/residence/reglement' });
	await expect(page.getByText(FICHIER.titre)).toBeVisible();
	await expect(page.getByText(/Section visible de l'administration seule/)).toBeVisible();
	await expect(
		page.getByRole('link', { name: 'consulter le règlement de copropriété' }),
	).toHaveCount(0);
});

test('fermé, l’onglet disparaît et son adresse ramène à la Fiche', async ({ page }) => {
	await ouvrir(page, { compte: COPROPRIETAIRE, acces: false, adresse: '/residence/reglement' });
	await expect(page).toHaveURL(/\/residence$/);
	await expect(ongletReglement(page)).toHaveCount(0);
});

test('le conseil syndical publie une réponse dans la FAQ', async ({ page }) => {
	await ouvrir(page, { compte: MEMBRE_CS, acces: true, adresse: '/residence/reglement' });
	await expect(page.getByRole('heading', { name: 'Questions posées' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Publier dans la FAQ' })).toBeVisible();
	//  Le conseil lit le lien, comme les copropriétaires — pas les fichiers.
	await expect(page.getByText(FICHIER.titre)).toHaveCount(0);
	await expect(
		page.getByRole('link', { name: 'consulter le règlement de copropriété' }),
	).toBeVisible();
});

test('l’ancienne adresse de l’Espace CS mène à Ma résidence, ancre comprise', async ({ page }) => {
	await ouvrir(page, {
		compte: MEMBRE_CS,
		acces: true,
		adresse: '/espace-cs/reglement#question-reglement-3',
	});
	await expect(page).toHaveURL(/\/residence\/reglement#question-reglement-3$/);
	await expect(page.getByText(QUESTION.question)).toBeVisible();
});
