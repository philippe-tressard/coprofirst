/*
 *  **La conciliation d'une fusion refusée pour fuite de lecture** (27/10/2026).
 *
 *  Demandé : « quand on veut fusionner 2 affaires liées, la fusion est parfois
 *  refusée car une section diffère, notamment le périmètre : proposer un plan de
 *  conciliation pour autoriser la fusion ».
 *
 *  Le test lit l'écran réel, API simulée, depuis la correction d'une affaire :
 *  - l'écart (le périmètre) est montré, avec les trois options et ce que chacune
 *    ferait lire ;
 *  - ÉLARGIR exige la confirmation nominative : « Continuer » reste fermé tant
 *    que les noms ne sont pas confirmés, puis la fusion part avec LEUR liste ;
 *  - INVERSER fait absorber l'autre : `principale_id` part avec la fusion ;
 *  - une option indisponible dit pourquoi, et ne se choisit pas.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const NOMS = ['Résident Un', 'Résident Deux'];
const PERSONNES = NOMS.map((nom, i) => ({ id: 7 + i, nom }));

//  60 est corrigée (la plus récente) ; 61, la plus ancienne, absorberait.
const ANCIENNE = {
	id: 61,
	numero: 'TK-A00061',
	titre: 'Tache au plafond du logement du dessous',
	statut: 'ouvert',
	cree_le: '2026-09-10T08:00:00Z',
};

const AFFAIRE = {
	id: 60,
	numero: 'TK-A00060',
	titre: 'Fuite sous l’évier du troisième',
	description: '<p>De l’eau coule sous l’évier.</p>',
	categorie: 'question',
	statut: 'en_cours',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	public_cible: [],
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	natures: ['activite'],
	affaires_liees: [ANCIENNE],
	cree_le: '2026-09-20T10:00:00Z',
	mis_a_jour_le: '2026-09-20T10:00:00Z',
};

const OPTION_VIDE = {
	disponible: true,
	pourquoi: null,
	exposes: [],
	perdants: 0,
	resultat: null,
	consentement: false,
};

//  Le verdict de la fusion pour 60, face à 61 qui absorberait : 60 est lue du seul bât. 2.
const VERDICT_60 = {
	id: 60,
	numero: AFFAIRE.numero,
	titre: AFFAIRE.titre,
	statut: AFFAIRE.statut,
	cree_le: AFFAIRE.cree_le,
	fusionnable: false,
	motif: "lue par moins de monde que l'affaire qui l'absorberait",
	conciliation: {
		ecarts: [
			{
				champ: 'perimetre',
				libelle: 'Périmètre',
				principale: 'Bât. 1',
				absorbee: 'Bât. 2',
			},
		],
		options: [
			{
				...OPTION_VIDE,
				code: 'inverser',
				libelle: "Inverser : l'autre affaire absorbe",
				disponible: false,
				pourquoi: 'L’autre affaire serait lue par des personnes qui ne lisent pas celle-ci.',
			},
			{
				...OPTION_VIDE,
				code: 'restreindre',
				libelle: 'Restreindre à ce que les deux affaires avaient en commun',
				disponible: false,
				pourquoi: 'Les deux périmètres n’ont rien en commun.',
			},
			{
				...OPTION_VIDE,
				code: 'elargir',
				libelle: 'Élargir à l’union des deux',
				exposes: PERSONNES,
				perdants: 0,
				consentement: true,
				resultat: { perimetre: 'Bât. 1 · Bât. 2', destinataires: 'Tous', acces: 'Ouverte' },
			},
		],
	},
};

const PRINCIPALE = { ...AFFAIRE, ...ANCIENNE, affaires_liees: [], titre: 'Fuite et tache' };

async function ouvrirLaBoite(page: Page, verdict = VERDICT_60) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [AFFAIRE];
		if (chemin === '/api/tickets/60') return AFFAIRE;
		if (chemin === '/api/tickets/61') return PRINCIPALE;
		if (chemin === '/api/tickets/60/fusion')
			return [{ ...ANCIENNE, fusionnable: true, motif: null, conciliation: null }];
		if (chemin === '/api/suivi-affaires/fusions/conciliation') return [verdict];
		if (chemin === '/api/suivi-affaires/fusions/proposition')
			return { titre: PRINCIPALE.titre, description: '<p>Les deux.</p>', assiste_ia: false };
		if (chemin === '/api/suivi-affaires/fusions') return { principale_id: 61, absorbees: [60] };
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.locator('.carte-liste').first().getByText(AFFAIRE.titre).click();
	await page.getByRole('button', { name: 'Modifier', exact: true }).first().click();
	await page.getByRole('button', { name: 'Fusionner', exact: true }).first().click();
	const boite = page.getByRole('dialog', { name: 'Fusionner les affaires liées' });
	await expect(boite).toBeVisible();
	return boite;
}

const envoi = (page: Page) =>
	page.waitForRequest(
		(r) => r.method() === 'POST' && new URL(r.url()).pathname === '/api/suivi-affaires/fusions',
	);

test('l’écart est montré, et une option impossible dit pourquoi', async ({ page }) => {
	const boite = await ouvrirLaBoite(page);
	await expect(boite).toContainText('Périmètre');
	await expect(boite).toContainText('Bât. 1');
	await expect(boite).toContainText('Bât. 2');
	await expect(boite.getByText('Les deux périmètres n’ont rien en commun.')).toBeVisible();
	await expect(boite.getByRole('radio', { name: /Restreindre/ })).toBeDisabled();
	await expect(boite.getByRole('radio', { name: /Inverser/ })).toBeDisabled();
	//  Rien n'est choisi : on ne peut pas continuer sans fusionner autre chose.
	await expect(boite.getByRole('button', { name: 'Continuer' })).toBeDisabled();
});

test('élargir exige la confirmation nominative, puis la fusion part avec cette liste', async ({
	page,
}) => {
	const boite = await ouvrirLaBoite(page);
	await boite.getByRole('radio', { name: /Élargir/ }).check();
	for (const nom of NOMS) await expect(boite.getByText(nom)).toBeVisible();

	const continuer = boite.getByRole('button', { name: 'Continuer' });
	await expect(continuer).toBeDisabled();
	await boite.getByRole('checkbox', { name: /Je confirme/ }).check();
	await expect(continuer).toBeEnabled();
	await continuer.click();

	await expect(boite.locator('input[type="text"]')).toHaveValue(PRINCIPALE.titre);
	const requete = envoi(page);
	await boite.getByRole('button', { name: 'Enregistrer' }).click();
	const corps = (await requete).postDataJSON();
	expect(corps).toMatchObject({
		ids: [61, 60],
		conciliations: [{ affaire_id: 60, option: 'elargir', confirmes: PERSONNES.map((p) => p.id) }],
	});
	expect(corps.principale_id).toBeUndefined();
});

test('inverser fait absorber l’autre affaire : la principale choisie part avec la fusion', async ({
	page,
}) => {
	const inversable = {
		...VERDICT_60,
		conciliation: {
			...VERDICT_60.conciliation,
			options: VERDICT_60.conciliation.options.map((o) =>
				o.code === 'inverser' ? { ...o, disponible: true, pourquoi: null } : o,
			),
		},
	};
	const boite = await ouvrirLaBoite(page, inversable);
	await boite.getByRole('radio', { name: /Inverser/ }).check();
	await boite.getByRole('button', { name: 'Continuer' }).click();

	//  60 absorbe 61 : elle passe en tête, et le texte ne dit plus « la plus ancienne ».
	await expect(boite).toContainText(`${AFFAIRE.numero} absorbe ${ANCIENNE.numero}`);
	const requete = envoi(page);
	await boite.getByRole('button', { name: 'Enregistrer' }).click();
	expect((await requete).postDataJSON()).toMatchObject({ ids: [60, 61], principale_id: 60 });
});

test('laisser l’affaire hors de la fusion : rien à fusionner, on ne continue pas', async ({
	page,
}) => {
	const boite = await ouvrirLaBoite(page);
	await boite.getByRole('radio', { name: /Élargir/ }).check();
	await boite.getByRole('radio', { name: /La laisser hors de la fusion/ }).check();
	await expect(boite.getByRole('checkbox', { name: /Je confirme/ })).toHaveCount(0);
	await expect(boite.getByRole('button', { name: 'Continuer' })).toBeDisabled();
});
