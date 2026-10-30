/*
 *  **Ma résidence › Règlement — l'onglet ouvert aux copropriétaires (11/10/2026).**
 *
 *  Venu de l'Espace CS. Ce que ces tests tiennent, sur le VRAI écran, API simulée :
 *
 *  • un copropriétaire voit l'onglet quand l'administration le lui a ouvert, et
 *    seulement alors — fermé, l'onglet disparaît et son adresse ramène à la Fiche ;
 *  • il y lit une phrase et le lien vers le règlement publié, jamais les fichiers
 *    que l'assistant lit, et ses questions sans l'icône de publication en FAQ ;
 *  • l'administration, seule, voit ces fichiers et leur provenance ; le crayon
 *    ouvre le formulaire standard — Provenance, Pièces jointes, Annuler et
 *    Enregistrer (arbitré sur maquette le 11/10/2026) ;
 *  • l'avis s'ouvre sur sa mention, en italique : la provenance du texte, jamais
 *    son coût ni la date de chargement des fichiers ;
 *  • la corbeille suit `peut_supprimer` (son auteur, l'administration), et la
 *    question paraît au fil d'activité, verdict teinté, lien vers l'onglet ;
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
	categorie_ag_id: null,
	provenance: null,
};
/** …et à l'administration : la catégorie où joindre les fichiers, pas de lien. */
const PROVENANCE = 'la numérisation du règlement et de ses modificatifs de 1995 et 2005';
const ETAT_ADMIN = {
	...ETAT_LECTEUR,
	lien_reglement: null,
	categorie_id: 40,
	//  Sans catégorie des décisions : `/api/documents` simulé rend le même fichier
	//  à toute catégorie, et il s'afficherait deux fois.
	categorie_ag_id: null,
	provenance: PROVENANCE,
};

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

/** `QuestionReglement` — sans modèle, comme pour un copropriétaire. */
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
	provenance: PROVENANCE,
	auteur_nom: 'Jean Dupont',
	modele: null,
	faq_item_id: null,
	peut_supprimer: false,
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

test('l’avis s’ouvre sur sa mention en italique : la provenance, ni coût ni date de chargement', async ({
	page,
}) => {
	await ouvrir(page, { compte: COPROPRIETAIRE, acces: true, adresse: '/residence/reglement' });
	await page.getByText(QUESTION.question).click();
	const corps = page.locator('#question-reglement-3 .carte-corps');
	const mention = corps.locator('p').first();
	await expect(mention).toContainText('Avis indicatif');
	await expect(mention).toContainText(`Rédigé d'après ${PROVENANCE}.`);
	await expect(mention).toHaveCSS('font-style', 'italic');
	await expect(corps).not.toContainText('Coût');
	await expect(corps).not.toContainText('texte chargé');
});

test('l’administration modifie le texte au crayon : Annuler, puis Enregistrer', async ({
	page,
}) => {
	await ouvrir(page, { compte: ADMIN, acces: true, adresse: '/residence/reglement' });
	const envois: unknown[] = [];
	await page.route('**/api/reglement/provenance', (route) => {
		const corps = route.request().postDataJSON() as { provenance: string };
		envois.push(corps);
		return route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({ ...ETAT_ADMIN, provenance: corps.provenance }),
		});
	});
	await expect(page.getByText(PROVENANCE)).toBeVisible();
	const crayon = page.getByRole('button', { name: 'Modifier le texte du règlement' });
	const champ = page.getByLabel('Provenance');

	await crayon.click();
	await expect(champ).toHaveValue(PROVENANCE);
	await champ.fill('Autre provenance');
	await page.getByRole('button', { name: 'Annuler', exact: true }).click();
	await expect(champ).toHaveCount(0);
	await expect(page.getByText(PROVENANCE)).toBeVisible();
	expect(envois).toEqual([]);

	await crayon.click();
	await champ.fill('la numérisation du règlement');
	await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	await expect(champ).toHaveCount(0);
	await expect(page.getByText('la numérisation du règlement', { exact: true })).toBeVisible();
	expect(envois).toEqual([{ provenance: 'la numérisation du règlement' }]);
});

test('la corbeille suit ce que le serveur permet : l’auteur la voit', async ({ page }) => {
	const corbeille = page.getByRole('button', { name: 'Supprimer la question' });
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return COPROPRIETAIRE;
		if (chemin === '/api/reglement') return ETAT_LECTEUR;
		if (chemin === '/api/reglement/questions') return [{ ...QUESTION, peut_supprimer: true }];
	});
	await page.goto('/residence/reglement');
	await attendreHydratation(page);
	await expect(corbeille).toBeVisible();
	//  Le conseil syndical, sur la question d'un autre : pas de corbeille.
	await ouvrir(page, { compte: MEMBRE_CS, acces: true, adresse: '/residence/reglement' });
	await expect(page.getByText(QUESTION.question)).toBeVisible();
	await expect(corbeille).toHaveCount(0);
});

test('la question paraît au fil d’activité, verdict teinté, et mène à l’onglet', async ({
	page,
}) => {
	const maintenant = new Date().toISOString().slice(0, 19);
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return COPROPRIETAIRE;
		if (chemin === '/api/flux')
			return {
				items: [
					{
						id: 'qr_3',
						type: 'question_reglement',
						date: maintenant,
						cree_le: maintenant,
						titre: QUESTION.question,
						detail: 'Question au règlement — Oui, après autorisation de l’assemblée.',
						badges: ['Oui, sous conditions'],
						icon: '⚖️',
						lien: '/residence/reglement#question-reglement-3',
						meta: { question_reglement_id: 3, verdict: 'sous_conditions', auteur: 'Jean Dupont' },
					},
				],
				sante: {},
			};
	});
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
	const carte = page.locator('.carte-liste', { hasText: QUESTION.question });
	await expect(carte).toBeVisible();
	await expect(carte).toContainText('RÈGL.');
	await expect(carte.locator('.badge', { hasText: 'Oui, sous conditions' })).toHaveClass(
		/badge-orange/,
	);
	await expect(carte).toContainText('✍️ Jean Dupont');
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

/** Un PV d'AG dont la transcription attend sa relecture (`PvTranscrit`, 29/10/2026). */
const TRANSCRIPTION = '## Résolution n° 7 — Fermeture des balcons. Adoptée.';
const PV_A_RELIRE = {
	pv_id: 12,
	titre: 'PV AG 2025',
	date_ag: '2025-06-12',
	transcription: {
		id: 5,
		statut: 'a_relire',
		statut_libelle: 'À relire',
		contenu: TRANSCRIPTION,
		erreur: null,
		cree_le: '2025-06-20T05:15:00',
		valide_le: null,
	},
};

test('l’administration relit une transcription de PV dans sa ligne, puis l’enregistre', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/reglement') return ETAT_ADMIN;
		if (chemin === '/api/documents') return [FICHIER];
		if (chemin === '/api/reglement/questions') return [];
		if (chemin === '/api/reglement/transcriptions') return { disponible: true, pvs: [PV_A_RELIRE] };
	});
	const envois: unknown[] = [];
	await page.route('**/api/reglement/transcriptions/5/valider', (route) => {
		envois.push(route.request().postDataJSON());
		return route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({ ...PV_A_RELIRE.transcription, statut: 'validee' }),
		});
	});
	await page.goto('/residence/reglement');
	await attendreHydratation(page);
	await expect(page.getByRole('heading', { name: "Transcription des PV d'AG" })).toBeVisible();
	await expect(page.getByText('À relire')).toBeVisible();
	const crayon = page.getByRole('button', { name: 'Relire la transcription' });
	await crayon.click();
	await expect(crayon).toHaveAttribute('aria-pressed', 'true');
	const champ = page.getByLabel('Résolutions transcrites');
	await expect(champ).toHaveValue(TRANSCRIPTION);
	await champ.fill(TRANSCRIPTION + ' Corrigé.');
	await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	await expect(champ).toHaveCount(0);
	expect(envois).toEqual([{ contenu: TRANSCRIPTION + ' Corrigé.' }]);
});
