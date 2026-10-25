/*
 *  **L'atelier de l'état descriptif** — Admin › Imports, source « État descriptif » (#2213).
 *
 *  Les promesses de l'écran, vérifiées contre l'API simulée (forme RÉELLE du
 *  serveur, le type `EtatDescriptif`) :
 *  - un constat bloquant tient le bouton « Appliquer » fermé, et le dit ;
 *  - la correspondance des lettres part telle qu'elle est saisie — ce que l'écran
 *    MONTRE est ce qui PART ;
 *  - appliquer passe par une confirmation, puis rend compte ;
 *  - l'assistant qui lit le règlement (#2218) : une confirmation, l'écran dit la
 *    lecture en cours, se relit seul et annonce l'issue.
 *  - un « à savoir » (somme qui ne tombe pas juste) ne ferme pas l'application, et la
 *    confirmation le rappelle (25/10/2026) ;
 *  - le tableau défile dans sa carte : la dernière clé s'atteint, la page ne déborde pas.
 *
 *  Lots et lettres fictifs.
 */
import type { Page } from '@playwright/test';
import type { BilanEtatDescriptif, EtatDescriptif } from '../src/lib/api/etat-descriptif';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

function etat(applicable: boolean): EtatDescriptif {
	return {
		importe_le: '2026-10-24T10:00:00',
		applique_le: null,
		cles: [{ code: 'generales', libelle: 'Générales', denominateur: 100 }],
		lignes: [
			{
				rang: 2,
				lot: '901',
				batiment: 'X',
				nature: 'T2',
				nature_lue: 'logement',
				numero_usage: null,
				niveau: '1',
				circulation: null,
				lot_origine: null,
				source: null,
				quotes: { generales: 60 },
			},
			{
				rang: 3,
				lot: '902',
				batiment: null,
				nature: 'Parking',
				nature_lue: 'parking',
				numero_usage: '5 & 6',
				niveau: '-2',
				circulation: 'X',
				lot_origine: null,
				source: null,
				quotes: { generales: 40 },
			},
		],
		constats: applicable
			? []
			: [
					{
						code: 'lettre',
						gravite: 'bloquant',
						message: 'Lettre de bâtiment sans correspondance : saisir la lettre de l’acte.',
						lots: [],
					},
				],
		lettres_citees: ['X'],
		batiments: [{ id: 1, libelle: 'Bât. 1', lettre_rcp: applicable ? 'X' : null }],
		applicable,
		ia_disponible: false,
		lecture_ia: null,
		erreur_ia: null,
	};
}

/** L'atelier pendant (ou après l'échec de) la lecture : rien de lu encore. */
function lecture(issue: 'en_cours' | 'echec'): EtatDescriptif {
	return {
		...etat(false),
		cles: [],
		lignes: [],
		constats: [],
		lettres_citees: [],
		ia_disponible: true,
		lecture_ia: issue,
		erreur_ia: issue === 'echec' ? 'L’assistant n’a pas rendu le tableau attendu.' : null,
	};
}

const BILAN: BilanEtatDescriptif = {
	lots: 2,
	cles_creees: 1,
	quotes_modifiees: 2,
	perimetres_modifies: 5,
};

const CLES_LARGES = [
	'Charges générales',
	'Bâtiment A',
	'Bâtiment C',
	'Bâtiment D',
	'Ascenseur A',
	'Ascenseur C',
	'Ascenseur D',
	'Escalier A',
	'Escalier C',
	'Escalier D',
	"Escalier A'",
	"Escalier C'",
	"Escalier D'",
];

/** Treize clés, dont une dont la somme ne tombe pas juste : applicable, avec un « à savoir ». */
function etatIncomplet(): EtatDescriptif {
	const base = etat(true);
	const cles = CLES_LARGES.map((libelle, i) => ({
		code: `cle-${i}`,
		libelle,
		denominateur: i === 0 ? 101 : 100,
	}));
	return {
		...base,
		cles,
		lignes: base.lignes.map((l) => ({
			...l,
			quotes: Object.fromEntries(cles.map((c) => [c.code, l.rang === 2 ? 60 : 40])),
		})),
		constats: [
			{
				code: 'somme',
				gravite: 'avertissement',
				message: '« Charges générales » : il en manque 1.',
				lots: [],
			},
		],
	};
}

async function ouvrir(page: Page, applicable: boolean, incomplet = false) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/lots/admin/etat-descriptif') {
			return incomplet ? etatIncomplet() : etat(applicable);
		}
		if (chemin === '/api/lots/admin/etat-descriptif/lettres') return etat(true);
		if (chemin === '/api/lots/admin/etat-descriptif/appliquer') return BILAN;
	});
	await page.goto('/admin?onglet=imports&source=etat-descriptif');
	await attendreHydratation(page);
}

test('un constat bloquant tient « Appliquer » fermé et le dit', async ({ page }) => {
	await ouvrir(page, false);
	await expect(page.getByText('Sans correspondance : X.')).toBeVisible();
	await expect(page.getByRole('button', { name: 'Appliquer au patrimoine' })).toBeDisabled();
	await expect(page.getByText('Un contrôle bloque')).toBeVisible();
});

test('la lettre saisie est celle qui part', async ({ page }) => {
	await ouvrir(page, false);
	await page.getByLabel('Bât. 1').fill('x');
	const envoi = page.waitForRequest(
		(r) => r.url().endsWith('/api/lots/admin/etat-descriptif/lettres') && r.method() === 'PUT',
	);
	await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	const corps = (await envoi).postDataJSON();
	expect(corps).toEqual({ correspondances: [{ batiment_id: 1, lettre_rcp: 'x' }] });
	await expect(page.getByRole('button', { name: 'Appliquer au patrimoine' })).toBeEnabled();
});

test('appliquer passe par une confirmation, puis rend compte', async ({ page }) => {
	await ouvrir(page, true);
	await page.getByRole('button', { name: 'Appliquer au patrimoine' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Appliquer', exact: true }).click();
	await expect(page.locator('.toast-success')).toContainText('2 lot(s) désigné(s)');
});

test('sans assistant, rien ne propose de lire le règlement', async ({ page }) => {
	await ouvrir(page, true);
	await expect(page.getByRole('button', { name: 'Remplir depuis le règlement' })).toHaveCount(0);
});

test('l’assistant lit le règlement : confirmation, lecture en cours, puis l’issue', async ({
	page,
}) => {
	await page.clock.install();
	let lectures = 0;
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/lots/admin/etat-descriptif/lire-reglement') return lecture('en_cours');
		if (chemin === '/api/lots/admin/etat-descriptif') {
			lectures += 1;
			//  1re lecture : l'atelier vide ; 2e (la relecture) : la lecture a abouti.
			return lectures === 1
				? { ...etat(true), importe_le: null, lignes: [], cles: [], ia_disponible: true }
				: { ...etat(true), ia_disponible: true, lecture_ia: 'terminee' };
		}
	});
	await page.goto('/admin?onglet=imports&source=etat-descriptif');
	await attendreHydratation(page);

	const envoi = page.waitForRequest(
		(r) => r.url().endsWith('/etat-descriptif/lire-reglement') && r.method() === 'POST',
	);
	await page.getByRole('button', { name: 'Remplir depuis le règlement' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Lancer la lecture' }).click();
	await envoi;
	await expect(page.getByRole('status')).toContainText("L'assistant lit le règlement");
	const bouton = page.getByRole('button', { name: 'L’assistant lit le règlement…' });
	await expect(bouton).toBeDisabled();
	await expect(bouton).toHaveAttribute('aria-busy', 'true');

	await page.clock.fastForward(10_000);
	await expect(page.locator('.toast-success')).toContainText('2 lot(s) lu(s) dans le règlement');
	await expect(page.getByRole('button', { name: 'Appliquer au patrimoine' })).toBeEnabled();
});

test('une lecture échouée le dit, sans contrôle ni bouton d’application', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/lots/admin/etat-descriptif') return lecture('echec');
	});
	await page.goto('/admin?onglet=imports&source=etat-descriptif');
	await attendreHydratation(page);
	await expect(page.getByRole('alert')).toContainText('pas rendu le tableau attendu');
	await expect(page.getByRole('button', { name: 'Appliquer au patrimoine' })).toHaveCount(0);
	await expect(page.getByRole('button', { name: 'Remplir depuis le règlement' })).toBeEnabled();
});

test('un « à savoir » ne ferme pas l’application, et la confirmation le rappelle', async ({
	page,
}) => {
	await ouvrir(page, true, true);
	await expect(page.getByRole('button', { name: 'Appliquer au patrimoine' })).toBeEnabled();
	await expect(page.getByText('Aucun contrôle ne bloque. 1 point(s) à savoir')).toBeVisible();
	await page.getByRole('button', { name: 'Appliquer au patrimoine' }).click();
	await expect(page.getByRole('dialog')).toContainText('1 point(s) à savoir ne bloquent pas');
});

test('le tableau défile dans sa carte : la dernière clé s’atteint, la page ne déborde pas', async ({
	page,
}) => {
	await ouvrir(page, true, true);
	const zone = page.getByRole('region', { name: /Lignes lues/ });
	await expect(zone.getByRole('columnheader', { name: /Escalier D'/ })).toBeAttached();
	//  Des en-têtes abrégés, le nom entier dans l'infobulle et pour les lecteurs d'écran.
	await expect(zone.locator('th[title^="Ascenseur A"]')).toContainText('Asc. A');
	//  La zone défile (le contenu la dépasse) sans élargir la page : les noms entiers des clés,
	//  posés en absolu, ancraient la page à la fin de la ligne et la rendaient trois fois plus large.
	const mesure = await zone.evaluate((el) => ({
		zone: el.clientWidth,
		contenu: el.scrollWidth,
		page: window.innerWidth,
		doc: document.documentElement.scrollWidth,
	}));
	expect(mesure.contenu).toBeGreaterThan(mesure.zone);
	expect(mesure.doc).toBeLessThanOrEqual(mesure.page);
	expect(mesure.zone).toBeLessThanOrEqual(mesure.page);
	await zone.evaluate((el) => (el.scrollLeft = el.scrollWidth));
	const derniere = zone.locator('thead th').last();
	const [boite, cadre] = await Promise.all([derniere.boundingBox(), zone.boundingBox()]);
	expect(boite!.x + boite!.width).toBeLessThanOrEqual(cadre!.x + cadre!.width + 1);
	//  La colonne Lot reste en place pendant que les clés défilent.
	const lot = zone.locator('thead th.lot');
	expect((await lot.boundingBox())!.x).toBeGreaterThanOrEqual(cadre!.x - 1);
	//  La ligne Somme dit l'écart que le contrôle signale.
	await expect(zone.locator('tfoot td.ecart').first()).toHaveText('100');
});
