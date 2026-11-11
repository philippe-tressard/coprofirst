/*
 *  **Corriger les Destinataires d'une affaire ne fige pas l'écran** (29/09/2026).
 *
 *  Signalé en production (v2.83.1) sur TK-A00017 : une Question passée en
 *  « Étude & travaux » en correction ; les pastilles de la catégorie étaient
 *  présélectionnées, on en ajoute une, on en retire une présélectionnée —
 *  l'onglet se fige : plus aucun script ne répond, pas même une capture.
 *
 *  Le test rejoue ce geste sur l'écran réel, API simulée, et exige que la page
 *  RÉPONDE après chaque clic (`page.evaluate` sous délai court : un fil
 *  principal bloqué n'y répond jamais) et qu'aucune erreur n'ait été levée.
 *
 *  ⚠️ Il n'a PAS reproduit le gel (29/09/2026) : ni sur `main` (v2.83.1, défaut
 *  occupants + bailleurs, la séquence exacte du signalement), ni sur `dev`, en
 *  serveur de développement comme en build de production, bureau et mobile,
 *  compte CS ou admin, arbre des périmètres réel, périmètre résidence ou
 *  bâtiment — et 240 clics aléatoires sur six catégories n'ont rien figé. La
 *  cause tient donc à une donnée de l'affaire réelle que la simulation n'a pas :
 *  #1463. Il reste le garde-fou du geste signalé.
 *
 *  30/09/2026 : la donnée réelle a été obtenue (`GET /api/tickets/50`) et
 *  rejouée telle quelle — sur `main` (v2.84.7) comme sur v2.83.1, depuis la
 *  liste (la fiche n'offre pas « Modifier ») : aucun gel, 3 à 9 ms par clic.
 *  Sa FORME est reprise ci-dessous, anonymisée.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, choisirPastille, expect, simulerApi, test } from './aides';

const QUESTION = {
	id: 50,
	numero: 'TK-A00017',
	titre: 'Réfection de la cage d’escalier',
	//  La FORME de l'affaire réelle (#1463, relevée le 30/09/2026), anonymisée :
	//  un long compte rendu en HTML riche — espaces insécables, gras, souligné —,
	//  et `public_cible` à `null`, pas `[]`. Le gel n'a été reproduit ni avec
	//  elle ni sans ; elle reste pour que le garde-fou exerce le vrai cas.
	description: Array.from(
		{ length: 16 },
		(_, i) =>
			`<p>${i + 1}.&nbsp;&nbsp;&nbsp; <strong>Point ${i + 1}&nbsp;</strong>: Décision – ` +
			`à <u>relancer</u> avant l’AG&nbsp;; «&nbsp;suite&nbsp;» =&gt; syndic.</p>`,
	).join(''),
	categorie: 'question',
	statut: 'ouvert',
	priorite: 'normale',
	auteur_id: 1,
	//  ✏️ Le crayon est SERVI (`peut_corriger`, #2633) : l'auteur le reçoit.
	peut_corriger: true,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	public_cible: null,
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	natures: ['activite'],
	cree_le: '2026-09-20T10:00:00',
	mis_a_jour_le: '2026-09-20T10:00:00',
};

/** La section Destinataires du formulaire. */
const section = (page: Page) =>
	page.locator('section.section-formulaire', {
		has: page.locator('.section-titre-texte', { hasText: 'Destinataires' }),
	});

const pastille = (page: Page, libelle: RegExp) =>
	section(page).locator('button', { hasText: libelle });

/** La page répond-elle encore ? Un fil principal bloqué ne rend jamais la main. */
async function repond(page: Page) {
	await expect(
		Promise.race([
			page.evaluate(() => true),
			new Promise((_, refus) => setTimeout(() => refus(new Error('page figée')), 3000)),
		]),
	).resolves.toBe(true);
}

//  Une exception de la page fait échouer le test : c'est la règle de tous les
//  specs (`test` de `./aides`, #1475), plus besoin de l'écouter ici.
async function corrigerEnEtude(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [QUESTION];
		if (chemin === '/api/tickets/50') return QUESTION;
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.locator('.carte-liste').first().getByText(QUESTION.titre).click();
	await page.getByRole('button', { name: 'Modifier', exact: true }).first().click();
	await choisirPastille(page, /Étude & travaux/);
	await expect(pastille(page, /Conseil syndical/)).toHaveClass(/active/);
}

test('Étude & travaux en correction : ajouter puis retirer un destinataire ne fige pas l’écran', async ({
	page,
}) => {
	await corrigerEnEtude(page);

	await pastille(page, /Copropriétaires occupants/).click();
	await repond(page);
	await expect(pastille(page, /Copropriétaires occupants/)).toHaveClass(/active/);

	//  Retirer la présélectionnée : le geste qui figeait l'onglet.
	await pastille(page, /Conseil syndical/).click();
	await repond(page);
	await expect(pastille(page, /Conseil syndical/)).not.toHaveClass(/active/);
	await expect(pastille(page, /Copropriétaires occupants/)).toHaveClass(/active/);

	//  Et dans l'autre ordre : le défaut revient, puis on le quitte encore.
	await pastille(page, /Conseil syndical/).click();
	await pastille(page, /Copropriétaires occupants/).click();
	await repond(page);
	await expect(pastille(page, /Conseil syndical/)).toHaveClass(/active/);
	await expect(section(page).locator('button.active')).toHaveCount(1);
});
