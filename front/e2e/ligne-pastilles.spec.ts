/*
 *  **Une affaire a la même dernière ligne sur sa carte et dans le fil.**
 *
 *  Arbitré à l'écran le 27/09/2026 : la ligne de la carte d'affaire fait la
 *  norme — catégorie, état, 🔹 périmètre, qui la lit, ⚡ urgence, marqueurs,
 *  #numéro, ✍️ auteur, ✨ IA — et le fil la rend à l'identique, sans 📌 (il a son
 *  bandeau « Épinglé »). Elles différaient sur neuf points.
 *
 *  `lint:pastilles` vérifie que les cartes passent par `PastillesAffaire` ; ce
 *  test-ci vérifie ce qu'on LIT : les deux écrans sont rendus avec la même
 *  affaire (API simulée, compte CS) et leurs lignes comparées.
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';

const LIGNE = {
	numero: 'TK-109008',
	categorie: 'panne',
	statut: 'en_cours',
	priorite: 'haute',
	debut: null,
	perimetre_cible: ['bat:1'],
	public_cible: null,
	reserve_perimetre: false,
	confidentiel: false,
	epingle: true,
	assiste_ia: true,
};
const AUTEUR = 'Jean-Hervé KERBRAT';
const AFFAIRE = {
	...LIGNE,
	id: 7,
	titre: 'Porte du hall',
	description: 'Elle ne ferme plus',
	auteur_id: 2,
	auteur_nom: AUTEUR,
	cree_le: '2026-09-26T10:00:00',
	mis_a_jour_le: '2026-09-26T10:00:00',
	photos_urls: [],
	fichiers_urls: [],
};
const FLUX = {
	items: [
		{
			id: 'tk_7',
			type: 'ticket_ouvert',
			date: '2026-09-26T10:00:00',
			titre: 'Porte du hall',
			detail: 'Elle ne ferme plus',
			badges: ['#TK-109008', 'Panne', 'urgent'],
			icon: '🛠️',
			meta: { ticket_id: 7, perimetre_codes: ['bat:1'], auteur: AUTEUR, affaire: LIGNE },
		},
	],
	sante: {},
};

const simuler = (page: Page) =>
	simulerApi(page, (chemin) => {
		if (chemin === '/api/flux') return FLUX;
		if (chemin === '/api/tickets') return [AFFAIRE];
	});

/** Le texte d'une ligne, espaces normalisés. */
const texte = async (page: Page, selecteur: string) => {
	const ligne = page.locator(selecteur).first();
	//  Rendue d'abord : `innerText` ne réessaie pas, il lirait l'instant (#1830).
	await expect(ligne).toBeVisible();
	return (await ligne.innerText()).replace(/\s+/g, ' ').trim();
};

test('le fil rend la ligne de la carte d’affaire, sans 📌', async ({ page }) => {
	await simuler(page);

	await page.goto('/tickets');
	const carte = await texte(page, '.carte-liste .ec-tags');
	//  Cas zéro : la ligne de référence porte bien ce qu'on compare.
	expect(carte, 'la carte d’affaire n’a pas rendu sa ligne').toContain('#TK-109008');
	expect(carte).toContain('⚡ Urgente');
	expect(carte).toContain(`✍️ ${AUTEUR}`);

	await page.goto('/tableau-de-bord');
	const fil = await texte(page, '.flux-groupes .ec-tags');
	expect(fil).toBe(
		carte
			.replace(/📌 Épinglée ?/, '')
			.replace(/\s+/g, ' ')
			.trim(),
	);
});

/*
 *  **Rien ne sort de la ligne, au téléphone compris** (27/09/2026, arbitré à
 *  l'écran) : la ligne défilait sans barre visible, et l'auteur — son dernier
 *  élément — se lisait « ✍️ Jear ». Au téléphone elle passe désormais à la ligne
 *  (`EnteteCarte`). Mesuré sur la carte la plus chargée du fichier : urgente,
 *  épinglée, périmètre, IA, et un nom d'auteur long.
 */
test('l’auteur se lit en entier sur la dernière ligne', async ({ page }) => {
	await simuler(page);
	await page.goto('/tickets');
	const tags = page.locator('.carte-liste .ec-tags').first();
	await expect(tags).toContainText(`✍️ ${AUTEUR}`);
	const debord = await tags.evaluate((el) => el.scrollWidth - el.clientWidth);
	expect(debord, 'la ligne déborde : ce qui dépasse ne se voit pas').toBeLessThanOrEqual(1);
	const carte = await page.locator('.carte-liste').first().boundingBox();
	const auteur = await tags.getByText(`✍️ ${AUTEUR}`).boundingBox();
	expect(auteur!.x + auteur!.width).toBeLessThanOrEqual(carte!.x + carte!.width);
});

/*
 *  **Les cartes de la communauté disent qui les lit** (#1373, arbitré le
 *  27/09/2026) : la pastille de lecture bleue a remplacé le badge orange des
 *  destinataires, ✨ ferme la ligne, et l'idée comme le sondage ne nomment pas
 *  leur auteur. Les valeurs sont celles que l'API rend (`_enrich` des annonces,
 *  listes de codes) — pas des formes inventées pour le test.
 */
const CIBLAGE = { perimetre_cible: [], public_cible: ['locataires'], assiste_ia: true };
const COMMUNAUTE: Record<string, unknown> = {
	'/api/annonces': [
		{
			...CIBLAGE,
			id: 3,
			titre: 'Vélo enfant',
			description: 'Bon état',
			type_annonce: 'don',
			statut: 'en_cours',
			categorie: 'divers',
			prix: null,
			negotiable: false,
			photos: [],
			auteur_prenom: 'Jeanne',
			auteur_nom: 'MARTIN',
			auteur_email: null,
			est_auteur: false,
			archivee: false,
			cree_le: '2026-09-26T10:00:00',
		},
	],
	'/api/idees': [
		{
			...CIBLAGE,
			id: 4,
			titre: 'Un composteur',
			description: 'Dans la cour',
			statut: 'ouverte',
			nb_votes: 2,
			mon_vote: false,
			auteur_id: 9,
			cree_le: '2026-09-26T10:00:00',
		},
	],
	'/api/sondages': [
		{
			...CIBLAGE,
			id: 5,
			question: 'Repeindre le hall ?',
			cloture: false,
			cloture_le: null,
			nb_votants: 3,
			auteur_id: 9,
			cree_le: '2026-09-26T10:00:00',
		},
	],
};

for (const [route, carte, auteur] of [
	['/annonces', '.carte-liste', '✍️ Jeanne MARTIN'],
	['/idees', '.carte-liste[id^="idee-"]', null],
	['/sondages', '.sondage-card', null],
] as const) {
	test(`${route} : pastille de lecture, ✨ en fin de ligne, auteur ${auteur ? 'nommé' : 'tu'}`, async ({
		page,
	}) => {
		await simulerApi(page, (chemin) => COMMUNAUTE[chemin]);
		await page.goto(route);
		const tags = page.locator(`${carte} .ec-tags`).first();
		//  Cas zéro : la carte est rendue, avec sa ligne.
		await expect(tags).toBeVisible();
		await expect(tags.locator('.pastille-lecture')).toContainText('Locataires');
		await expect(tags.locator('.badge-orange')).toHaveCount(0);
		const ligne = (await tags.innerText()).replace(/\s+/g, ' ').trim();
		expect(ligne.endsWith('✨'), `✨ ferme la ligne : « ${ligne} »`).toBe(true);
		if (auteur) expect(ligne).toContain(auteur);
		else expect(ligne).not.toContain('✍️');
	});
}
