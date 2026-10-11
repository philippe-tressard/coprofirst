/*
 *  **La gouttière des fiches de « Ma résidence »** (arbitré le 11/10/2026).
 *
 *  Chaque fiche se date par LE DOCUMENT, jamais par son dépôt :
 *
 *  | Fiche                   | Gouttière                      |
 *  |-------------------------|--------------------------------|
 *  | Règles & Recommandations | RÈGL., sans date              |
 *  | Plans                   | PLAN, sans date                |
 *  | Règlement               | date du document + RÈGL.       |
 *  | CR d'AG                 | date de l'AG + AG              |
 *  | Diagnostics             | date du rapport le plus récent + DIAG. |
 *
 *  Et la date d'un règlement est DEMANDÉE, PROPOSÉE (aujourd'hui) et modifiable.
 *  Avant ce lot, plans et règlement portaient `publie_le` — la date du dépôt.
 */
import type { Locator, Page, Request } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const CATEGORIES = [
	{ id: 11, code: 'plan_residence', nom: 'Plans' },
	{ id: 12, code: 'reglement_copropriete', nom: 'Règlement' },
	{ id: 13, code: 'pv_ag', nom: 'PV d’AG' },
];

const DEPOT = '2026-10-05T09:00:00';

function document(id: number, categorie: number, titre: string, champs: object = {}) {
	return {
		id,
		titre,
		description: '',
		fichier_nom: `${titre}.pdf`,
		mime_type: 'application/pdf',
		categorie_id: categorie,
		perimetre: 'résidence',
		publie_le: DEPOT,
		annee: null,
		date_ag: null,
		date_document: null,
		perimetre_cible: [],
		...champs,
	};
}

const PAR_CATEGORIE: Record<string, object[]> = {
	'11': [document(1, 11, 'Plan de masse')],
	'12': [document(2, 12, 'Règlement de 1998', { date_document: '1998-03-12' })],
	'13': [document(3, 13, 'PV AG 2025', { annee: 2025, date_ag: '2025-06-12' })],
};

const DIAGNOSTICS = [
	{
		id: 7,
		code: 'amiante',
		nom: 'Amiante',
		texte_legislatif: 'article R1334-14 du code de la santé publique.',
		frequence: '10 ans',
		ordre: 1,
		non_applicable: false,
		rapports: [
			{ id: 71, titre: 'Repérage 2019', date_rapport: '2019-04-02', publie_le: DEPOT },
			{ id: 72, titre: 'Repérage 2024', date_rapport: '2024-09-18', publie_le: DEPOT },
		].map((r) => ({
			...r,
			diagnostic_type_id: 7,
			fichier_nom: 'amiante.pdf',
			taille_octets: 10,
			mime_type: 'application/pdf',
			synthese: null,
		})),
	},
];

async function residence(page: Page): Promise<Request[]> {
	const depots: Request[] = [];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/documents/categories') return CATEGORIES;
		if (chemin === '/api/copropriete') return { id: 1, nom: 'Résidence témoin' };
		if (chemin === '/api/regles-residence')
			return [{ id: 5, titre: 'Couleur des volets', contenu: '', ordre: 1 }];
		if (chemin === '/api/diagnostics/types') return DIAGNOSTICS;
	});
	//  Enregistrée APRÈS `simulerApi` : Playwright essaie d'abord la dernière route.
	await page.route(
		(url) => url.pathname === '/api/documents',
		(route) => {
			const requete = route.request();
			if (requete.method() === 'POST') {
				depots.push(requete);
				return route.fulfill({ json: document(900, 12, 'Déposé') });
			}
			const categorie = new URL(requete.url()).searchParams.get('categorie_id') ?? '';
			return route.fulfill({ json: PAR_CATEGORIE[categorie] ?? [] });
		},
	);
	await page.goto('/residence');
	await attendreHydratation(page);
	return depots;
}

/** La gouttière de la carte qui porte ce titre. */
function gouttiere(page: Page, titre: string): Locator {
	return page.locator('.carte-liste', { hasText: titre }).locator('.gouttiere');
}

async function attendre(g: Locator, abrege: string, date: string | null) {
	await expect(g.locator('abbr')).toHaveText(abrege);
	if (date) await expect(g.locator('time')).toHaveAttribute('datetime', date);
	else await expect(g.locator('time')).toHaveCount(0);
}

test('chaque fiche se date par le document, jamais par son dépôt', async ({ page }) => {
	await residence(page);
	await attendre(gouttiere(page, 'Couleur des volets'), 'RÈGL.', null);
	await attendre(gouttiere(page, 'Plan de masse'), 'PLAN', null);
	await attendre(gouttiere(page, 'Règlement de 1998'), 'RÈGL.', '1998-03-12');
	await attendre(gouttiere(page, 'PV AG 2025'), 'AG', '2025-06-12');
	//  Le rapport le plus récent, quel que soit l'ordre reçu.
	await attendre(gouttiere(page, 'Amiante'), 'DIAG.', '2024-09-18');
});

test('la date d’un règlement est demandée, proposée et envoyée', async ({ page }) => {
	const depots = await residence(page);
	await page
		.locator('div')
		.filter({ has: page.getByRole('heading', { name: /Règlement de copropriété/ }) })
		.last()
		.getByRole('button', { name: /Ajouter/ })
		.click();
	const formulaire = page.getByRole('group', { name: 'Ajouter un règlement' });
	await formulaire
		.locator('input[type=file]')
		.first()
		.setInputFiles({ name: 'r.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF') });
	const date = formulaire.locator('#reglement-date-document');
	const enregistrer = formulaire.getByRole('button', { name: /Enregistrer/ });
	//  PROPOSÉE : le jour de Paris.
	const aujourdHui = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Paris' }).format(
		new Date(),
	);
	await expect(date).toHaveValue(aujourdHui);
	//  DEMANDÉE : vidée, rien ne part.
	await date.fill('');
	await expect(enregistrer).toBeDisabled();
	//  MODIFIABLE : la date saisie est celle qui part.
	await date.fill('1998-03-12');
	await enregistrer.click();
	await expect.poll(() => depots.length).toBe(1);
	expect(depots[0].postData()).toContain('name="date_document"\r\n\r\n1998-03-12\r\n');
});
