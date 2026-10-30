/*
 *  **Affaires liées, à la correction d'une affaire** (#2173, 23/10/2026).
 *
 *  Demandé : « en plus du N° et du titre, le suivi et la date de création », et
 *  « fusionner les affaires si au moins 2 affaires liées, en reprenant le
 *  principe complet de fusion déjà utilisé ».
 *
 *  Le test lit l'écran réel, API simulée, bureau ET téléphone :
 *  - chaque affaire liée est une ligne qui dit son suivi et sa date, et qui
 *    tient dans la largeur — aucun défilement horizontal de la page ;
 *  - « Fusionner » ouvre la boîte du Suivi des affaires (#2083), la PLUS
 *    ANCIENNE en tête : c'est elle qui absorbe ; la fusion part par la route du
 *    Suivi, puis la principale s'ouvre ;
 *  - une affaire close ne propose pas de fusion.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const LIEE = {
	id: 61,
	numero: 'TK-A00061',
	titre: 'Tache au plafond du logement du dessous',
	statut: 'ouvert',
	//  Plus ancienne que l'affaire corrigée : c'est elle qui absorbera.
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
	affaires_liees: [LIEE],
	cree_le: '2026-09-20T10:00:00Z',
	mis_a_jour_le: '2026-09-20T10:00:00Z',
};

const PRINCIPALE = { ...AFFAIRE, ...LIEE, affaires_liees: [], titre: 'Fuite et tache au plafond' };

/** La section « Affaires liées » du formulaire. */
const section = (page: Page) =>
	page.locator('section.section-formulaire', {
		has: page.locator('.section-titre-texte', { hasText: 'Affaires liées' }),
	});

async function corriger(page: Page, affaire: typeof AFFAIRE) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [affaire];
		if (chemin === '/api/tickets/60') return affaire;
		if (chemin === '/api/tickets/61') return PRINCIPALE;
		if (chemin === '/api/tickets/60/fusion')
			return [{ ...LIEE, fusionnable: true, motif: null, conciliation: null }];
		//  Le verdict de la fusion : la plus ancienne (61) absorbe, 60 est lisible de ses lecteurs.
		if (chemin === '/api/suivi-affaires/fusions/conciliation')
			return [{ ...AFFAIRE, fusionnable: true, motif: null, conciliation: null }];
		if (chemin === '/api/suivi-affaires/fusions/proposition')
			return { titre: PRINCIPALE.titre, description: '<p>Les deux.</p>', assiste_ia: false };
		if (chemin === '/api/suivi-affaires/fusions') return { principale_id: 61, absorbees: [60] };
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.locator('.carte-liste').first().getByText(affaire.titre).click();
	await page.getByRole('button', { name: 'Modifier', exact: true }).first().click();
	await expect(section(page)).toBeVisible();
}

test('une affaire liée dit son numéro, son titre, son suivi et sa date — sans déborder', async ({
	page,
}) => {
	await corriger(page, AFFAIRE);
	const ligne = section(page).locator('li.liee');
	await expect(ligne).toHaveCount(1);
	await expect(ligne).toContainText(LIEE.numero);
	await expect(ligne).toContainText(LIEE.titre);
	await expect(ligne.locator('.badge')).toHaveText('Ouvert');
	await expect(ligne).toContainText('créée le 10 sept. 2026');
	await expect(ligne.getByRole('button', { name: /Retirer le lien avec TK-A00061/ })).toBeVisible();

	//  La ligne tient dans la section, et la page ne défile pas de côté.
	const largeurs = await page.evaluate(() => ({
		page: document.documentElement.scrollWidth,
		vue: document.documentElement.clientWidth,
	}));
	expect(largeurs.page).toBeLessThanOrEqual(largeurs.vue);
	const boite = await ligne.boundingBox();
	expect(boite && boite.x + boite.width).toBeLessThanOrEqual(largeurs.vue);
});

test('« Fusionner » ouvre la boîte du Suivi, la plus ancienne absorbe, la principale s’ouvre', async ({
	page,
}) => {
	await corriger(page, AFFAIRE);
	await section(page).getByRole('button', { name: 'Fusionner', exact: true }).click();

	const boite = page.getByRole('dialog', { name: 'Fusionner les affaires liées' });
	await expect(boite).toBeVisible();
	//  La plus ancienne, nommée en tête, absorbe la plus récente.
	await expect(boite).toContainText(`${LIEE.numero}, la plus ancienne, absorbe ${AFFAIRE.numero}`);
	await expect(boite.locator('input[type="text"]')).toHaveValue(PRINCIPALE.titre);

	const envoi = page.waitForRequest(
		(r) => r.method() === 'POST' && new URL(r.url()).pathname === '/api/suivi-affaires/fusions',
	);
	await boite.getByRole('button', { name: 'Enregistrer' }).click();
	expect((await envoi).postDataJSON()).toMatchObject({ ids: [61, 60], titre: PRINCIPALE.titre });
	await expect(boite).toBeHidden();
	await expect(page).toHaveURL(/\/tickets\/61$/);
});

test('la correction s’ouvre dans la boîte de la page, comme la création — jamais dans une fenêtre', async ({
	page,
}) => {
	//  #2315 : `FormulaireTicket` pose son cadre par `CadreFormulaire` (`lint:cadre-geste`).
	//  La correction se rend dans la carte, sans bordure ni titre de boîte (#425).
	await corriger(page, AFFAIRE);
	const boite = page.locator('.formulaire-creation[role="group"]');
	await expect(boite).toHaveCount(1);
	await expect(boite.locator('input').first()).toHaveValue(AFFAIRE.titre);
	await expect(page.getByRole('dialog')).toHaveCount(0);
	await expect(boite.locator('h2')).toHaveCount(0);
});

test('une affaire close ne propose pas de fusion', async ({ page }) => {
	await corriger(page, { ...AFFAIRE, statut: 'résolu' });
	await expect(section(page).locator('li.liee')).toHaveCount(1);
	await expect(section(page).getByRole('button', { name: 'Fusionner', exact: true })).toHaveCount(
		0,
	);
});

test('un lien collé dans la recherche propose l’affaire qu’il désigne', async ({ page }) => {
	const AUTRE = { ...LIEE, id: 465, numero: 'TK-E00036', titre: 'Vote du changement de laine' };
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [AFFAIRE];
		if (chemin === '/api/tickets/60') return { ...AFFAIRE, affaires_liees: [] };
		if (chemin === '/api/tickets/choix') return [LIEE, AUTRE];
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.locator('.carte-liste').first().getByText(AFFAIRE.titre).click();
	await page.getByRole('button', { name: 'Modifier', exact: true }).first().click();
	await section(page)
		.getByPlaceholder('Numéro ou mots du titre')
		.fill('👉 Voir le contenu complet :\nhttps://5hostachy.fr/tickets/465?src=whatsapp');
	const propositions = section(page).getByRole('list', { name: 'Affaires proposées' });
	await expect(propositions.getByRole('button')).toHaveCount(1);
	await expect(propositions).toContainText(AUTRE.numero);
});
