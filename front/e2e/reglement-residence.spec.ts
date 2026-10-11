/*
 *  **Ma résidence › Règlement — l'onglet ouvert aux copropriétaires (11/10/2026).**
 *
 *  Venu de l'Espace CS. Ce que ces tests tiennent, sur le VRAI écran, API simulée :
 *
 *  • un copropriétaire voit l'onglet quand l'administration le lui a ouvert, et
 *    seulement alors — fermé, l'onglet disparaît et son adresse ramène à la Fiche ;
 *  • il y lit le titre du texte et les liens vers les ACTES, sans la fiche
 *    technique du texte, sans chargement ni choix d'actes, et ses questions sans
 *    l'icône de publication en FAQ ;
 *  • le conseil syndical, lui, publie ;
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

const ACTE = { id: 27, titre: 'Règlement numérisé', lien: '/residence#doc-27' };

/** `EtatReglement` tel que le serveur le rend à un copropriétaire. */
const ETAT_COPROPRIETAIRE = {
	disponible: true,
	texte: {
		id: 1,
		titre: 'Règlement fictif de la résidence',
		nom_fichier: null,
		nb_caracteres: null,
		charge_par: null,
		cree_le: '2026-10-01T10:00:00',
	},
	nb_versions: 1,
	documents: [ACTE],
	documents_candidats: null,
	documents_ids: null,
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
		if (chemin === '/api/reglement') return ETAT_COPROPRIETAIRE;
		if (chemin === '/api/reglement/questions') return [QUESTION];
	});
	await page.goto(adresse);
	await attendreHydratation(page);
}

const ongletReglement = (page: Page) => page.locator('.tabs').getByText('Règlement');

test('ouvert, le copropriétaire lit le texte, les actes et ses questions — sans geste du conseil', async ({
	page,
}) => {
	await ouvrir(page, { compte: COPROPRIETAIRE, acces: true, adresse: '/residence/reglement' });
	await expect(ongletReglement(page)).toBeVisible();
	await expect(page.getByText('Règlement fictif de la résidence')).toBeVisible();
	await expect(page.getByRole('link', { name: ACTE.titre })).toHaveAttribute('href', ACTE.lien);
	await expect(page.getByText(/interrogez le conseil syndical/)).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Vos questions' })).toBeVisible();
	await expect(page.getByText(QUESTION.question)).toBeVisible();
	//  Ce que le serveur lui refuserait, l'écran ne le propose pas.
	await expect(page.getByRole('button', { name: 'Publier dans la FAQ' })).toHaveCount(0);
	await expect(page.getByText('Actes montrés à côté du texte')).toHaveCount(0);
	await expect(page.getByText(/Charger le texte|Charger une nouvelle version/)).toHaveCount(0);
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
