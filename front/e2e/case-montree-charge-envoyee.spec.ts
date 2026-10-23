/*
 *  **Une case montrée est une case envoyée** (#2142, #2144 — audit du 22/10/2026).
 *
 *  Le 22/10/2026, « Réservé au périmètre » était montrée cochée sur une affaire
 *  et partait `false` : un code d'ascenseur a été lu de toute la résidence et
 *  posté sur le groupe WhatsApp. L'audit du soir même a trouvé la même forme sur
 *  « Répondre » : Périmètre, Destinataires et Diffusion étaient rendus, et la
 *  requête ne portait que `contenu`, `interne` et `fichiers_urls` — un membre du
 *  conseil qui passait les Destinataires au conseil croyait avoir fermé
 *  l'affaire.
 *
 *  Ce test ne vérifie pas qu'un formulaire « marche » : il lit ce que l'écran
 *  MONTRE, puis ce que la requête EMPORTE. Pour chaque formulaire, `CASES` dit,
 *  case par case, le champ de la charge qui la reflète. Une case rendue qui n'y
 *  figure pas échoue — c'est une case montrée dont personne n'a dit où elle part.
 *  Une case déclarée qui ne se rend plus échoue aussi : la table ne décrirait
 *  plus l'écran.
 *
 *  Les cases de RESTRICTION (#2144) : « Réservé au périmètre » (affaire et
 *  actualité) et « Confidentielle » (actualité) à la création, ici ; « Message
 *  interne » de la réponse, ici ; « CS et présents » du compte rendu d'une
 *  affaire, dans le parcours de `point-conseil.spec.ts`, qui en a les données.
 *
 *  `standards/11` §15 : ce que l'écran montre est ce qui part.
 */
import type { Locator, Page } from '@playwright/test';
import type { Perimetre } from '../src/lib/perimetres';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const AFFAIRE = {
	id: 7,
	numero: 'TK-124291',
	titre: 'Ascenseur en panne',
	description: 'Il reste bloqué au deuxième.',
	categorie: 'panne',
	statut: 'ouvert',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['bat:1'],
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	natures: ['activite'],
	cree_le: '2026-10-20T10:00:00',
	mis_a_jour_le: '2026-10-21T10:00:00',
};

/** Une case du formulaire et le champ de la charge qui doit la refléter. */
interface CaseDeclaree {
	/** Le libellé de la case, tel que l'écran le rend. */
	libelle: RegExp;
	/** Ce que la charge doit porter une fois la case cochée (et son champ rempli). */
	attendu: Record<string, unknown>;
}

/**
 *  « Répondre » : la route (`MessageCreate`) ne porte que le contenu, `interne`,
 *  les pièces et l'adresse externe. Rien d'autre ne se montre.
 */
const CASES_REPONSE: CaseDeclaree[] = [{ libelle: /Message interne/, attendu: { interne: true } }];

/** Le libellé d'une case : son `<label>` enveloppant, ou celui qui la nomme par `for`. */
async function libelleDe(formulaire: Locator, c: Locator): Promise<string> {
	const enveloppe = c.locator('xpath=ancestor::label[1]');
	if ((await enveloppe.count()) > 0) return (await enveloppe.innerText()).trim();
	const id = await c.getAttribute('id');
	return id ? (await formulaire.locator(`label[for="${id}"]`).innerText()).trim() : '';
}

/**
 *  Les libellés de toutes les cases que le formulaire REND — section par section :
 *  les sections facultatives sont pliées, et un seul bloc se déplie à la fois
 *  (`$lib/accordeon`). Compter sans déplier rendrait « aucune case » vert pour
 *  une section qui en cache trois.
 */
async function casesRendues(formulaire: Locator): Promise<string[]> {
	const libelles = new Set<string>();
	const relever = async () => {
		for (const c of await formulaire.getByRole('checkbox').all()) {
			if (await c.isVisible()) libelles.add(await libelleDe(formulaire, c));
		}
	};
	await relever();
	//  Repérées par la région qu'elles ouvrent : le bouton change à chaque pli.
	const regions = new Set<string>();
	for (const pli of await formulaire.locator('button[aria-controls]').all()) {
		const id = await pli.getAttribute('aria-controls');
		if (id) regions.add(id);
	}
	expect(regions.size, 'aucune section pliable : le relevé ne verrait rien').toBeGreaterThan(0);
	for (const id of regions) {
		const plie = formulaire.locator(`button[aria-controls="${id}"][aria-expanded="false"]`);
		if ((await plie.count()) > 0) {
			await plie.first().click();
			//  Lire une fois la section OUVERTE — son bouton plié a disparu —,
			//  jamais pendant le geste.
			await expect(plie).toHaveCount(0);
		}
		await relever();
	}
	return [...libelles];
}

async function ouvrirLaReponse(page: Page): Promise<{ formulaire: Locator; envois: unknown[] }> {
	const envois: unknown[] = [];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets/7') return AFFAIRE;
	});
	//  Enregistrée APRÈS : Playwright essaie la dernière route d'abord.
	await page.route(
		(url) => url.pathname === '/api/tickets/7/messages',
		(route) => {
			if (route.request().method() !== 'POST') return route.fallback();
			envois.push(route.request().postDataJSON());
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					id: 90,
					ticket_id: 7,
					contenu: '<p>Réponse</p>',
					interne: false,
					cree_le: '2026-10-22T10:00:00',
					fichiers_urls: [],
				}),
			});
		},
	);
	await page.goto('/tickets/7');
	await attendreHydratation(page);
	//  Le bouton sous le fil des messages : l'icône de la carte (exactement
	//  « Répondre ») ouvre le même formulaire — `repondre-depuis-la-carte.spec.ts`.
	await page
		.locator('.carte-repondre')
		.getByRole('button', { name: /Répondre/ })
		.click();
	const formulaire = page.getByRole('group', { name: 'Répondre' });
	await expect(formulaire.getByRole('button', { name: 'Enregistrer' })).toBeVisible();
	return { formulaire, envois };
}

test('« Répondre » ne montre ni Périmètre, ni Destinataires, ni les canaux de diffusion', async ({
	page,
}) => {
	const { formulaire } = await ouvrirLaReponse(page);
	await expect(formulaire.getByRole('group', { name: /^Périmètre/ })).toHaveCount(0);
	await expect(formulaire.getByRole('group', { name: /^Destinataires/ })).toHaveCount(0);
	const rendues = await casesRendues(formulaire);
	for (const canal of [/Partager sur le groupe/, /Envoyer au syndic/, /Envoyer au Conseil/]) {
		expect(rendues.filter((l) => canal.test(l))).toEqual([]);
	}
});

test('« Répondre » : chaque case rendue est déclarée, et part dans la charge', async ({ page }) => {
	const { formulaire } = await ouvrirLaReponse(page);
	const rendues = await casesRendues(formulaire);
	const nonDeclarees = rendues.filter((l) => !CASES_REPONSE.some((c) => c.libelle.test(l)));
	expect(nonDeclarees, 'case montrée sans champ déclaré dans la charge').toEqual([]);
	for (const c of CASES_REPONSE) {
		expect(
			rendues.some((l) => c.libelle.test(l)),
			`case déclarée qui ne se rend plus : ${c.libelle}`,
		).toBe(true);
	}
});

for (const c of CASES_REPONSE) {
	test(`« Répondre » : ${c.libelle.source} cochée part dans la charge`, async ({ page }) => {
		const { formulaire, envois } = await ouvrirLaReponse(page);
		await formulaire.getByRole('textbox', { name: /Commentaire/ }).fill('Réponse');
		await formulaire.getByRole('button', { name: /^Diffusion/ }).click();
		await formulaire.getByRole('checkbox', { name: c.libelle }).check();
		await formulaire.getByRole('button', { name: 'Enregistrer' }).click();
		await expect.poll(() => envois.length).toBe(1);
		expect(envois[0]).toMatchObject(c.attendu);
	});
}

test('« Répondre » : l’adresse externe saisie part dans la charge', async ({ page }) => {
	const { formulaire, envois } = await ouvrirLaReponse(page);
	await formulaire.getByRole('textbox', { name: /Commentaire/ }).fill('Réponse');
	await formulaire.getByRole('button', { name: /^Diffusion/ }).click();
	await formulaire
		.getByRole('textbox', { name: /Notifier une adresse email externe/ })
		.fill('gardien@exemple.test');
	await formulaire.getByRole('button', { name: 'Enregistrer' }).click();
	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0]).toMatchObject({ email_externe: 'gardien@exemple.test' });
});

//  ── La création d'une affaire : les deux cases qui RESTREIGNENT la lecture ──
//  Ce sont elles que l'incident du 22/10 a trompées : chacune doit partir dans
//  le champ qu'elle nomme, et elle seule.

function noeud(champs: Partial<Perimetre> & Pick<Perimetre, 'id' | 'code' | 'libelle'>): Perimetre {
	return {
		parent: null,
		libelle_court: champs.libelle,
		description: '',
		icone: null,
		batiment_id: null,
		profondeur: 0,
		ordre: 0,
		actif: true,
		portee_globale: false,
		concerne_tous: false,
		selectionnable: true,
		privatif: false,
		hors_copropriete: false,
		utilise: false,
		nb_descendants: 0,
		dupliquable: false,
		...champs,
	};
}

const ARBRE: Perimetre[] = [
	noeud({
		id: 1,
		code: 'résidence',
		libelle: 'Résidence',
		portee_globale: true,
		concerne_tous: true,
	}),
	noeud({
		id: 2,
		code: 'bat:1',
		libelle: 'Bâtiment 1',
		ordre: 1,
		batiment_id: 1,
	}),
];

/** Une case de restriction, la nature qui l'offre, et le champ qui la reflète. */
interface CaseDeRestriction extends CaseDeclaree {
	/** La catégorie choisie, par sa description dans la grille. */
	nature: RegExp;
}

const CASES_RESTRICTION: CaseDeRestriction[] = [
	{
		nature: /Ascenseur, chauffage, éclairage/,
		libelle: /Réservé au périmètre sélectionné/,
		attendu: { reserve_perimetre: true },
	},
	{
		nature: /Information — suivi optionnel/,
		libelle: /Réservé au périmètre sélectionné/,
		attendu: { reserve_perimetre: true },
	},
	{
		nature: /Information — suivi optionnel/,
		libelle: /Confidentielle/,
		attendu: { confidentiel: true },
	},
];

async function nouvelleAffaire(
	page: Page,
	nature: RegExp,
): Promise<{ formulaire: Locator; envois: unknown[] }> {
	const envois: unknown[] = [];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/perimetres') return ARBRE;
	});
	await page.route(
		(url) => url.pathname === '/api/tickets',
		(route) => {
			if (route.request().method() !== 'POST') return route.fallback();
			envois.push(route.request().postDataJSON());
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({ ...AFFAIRE, id: 8 }),
			});
		},
	);
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();
	await page.getByText(nature).first().click();
	const formulaire = page.getByRole('group', { name: /^Nouvelle (affaire|actualité)$/ });
	await formulaire.getByRole('textbox', { name: /^Titre/ }).fill('Code de l’ascenseur');
	await formulaire
		.getByRole('textbox', { name: /^Description/ })
		.fill('Nouveau code : à ne pas diffuser.');
	await formulaire.getByRole('button', { name: 'Bâtiment 1' }).click();
	return { formulaire, envois };
}

/**
 *  Enregistrer — et confirmer l'aperçu « Avant d'envoyer » quand il s'ouvre (une
 *  affaire qui diffuse ; une actualité qui ne diffuse rien part sans lui).
 *  Rend la charge postée.
 */
async function enregistrer(page: Page, formulaire: Locator, envois: unknown[]): Promise<unknown> {
	await formulaire.getByRole('button', { name: 'Enregistrer' }).click();
	const confirmer = page
		.getByRole('dialog', { name: /Avant d'envoyer/ })
		.getByRole('button', { name: 'Confirmer et envoyer' });
	await expect
		.poll(async () => {
			if (envois.length === 0 && (await confirmer.isVisible())) await confirmer.click();
			return envois.length;
		})
		.toBe(1);
	return envois[0];
}

for (const c of CASES_RESTRICTION) {
	test(`Nouvelle affaire (${c.nature.source}) : ${c.libelle.source} cochée part dans la charge`, async ({
		page,
	}) => {
		const { formulaire, envois } = await nouvelleAffaire(page, c.nature);
		const caseRendue = formulaire.getByRole('checkbox', { name: c.libelle });
		await caseRendue.check();
		//  Ce que l'écran MONTRE, avant d'envoyer : la case cochée.
		await expect(caseRendue).toBeChecked();
		expect(await enregistrer(page, formulaire, envois)).toMatchObject(c.attendu);
	});
}

test('Nouvelle affaire : rien de coché, rien de restreint', async ({ page }) => {
	const { formulaire, envois } = await nouvelleAffaire(page, CASES_RESTRICTION[0].nature);
	await expect(formulaire.getByRole('checkbox', { name: /Réservé/ })).not.toBeChecked();
	expect(await enregistrer(page, formulaire, envois)).toMatchObject({ reserve_perimetre: false });
});
