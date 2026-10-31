/*
 *  **L'accueil : la frise du fil et le lien vers les consignes** (#779, 01/10/2026).
 *
 *  Deux factorisations, tenues ici par ce que l'utilisateur VOIT :
 *
 *  - `FriseDuFil` rend désormais les trois listes du fil — l'Épinglé, le fil
 *    récent et les Archives —, que la page et `ArchivesDuFil` écrivaient chacune
 *    de leur côté. Une carte se déplie au clic, une seule à la fois, dans
 *    chacune des trois.
 *  - `LienConsignes` rend le lien vers la fiche des consignes, écrit trois fois
 *    avec deux libellés : l'accueil et l'annuaire disent maintenant la même
 *    chose, vers la même adresse.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const ADRESSE = '/api/admin/fiche-arrivant';
const LIBELLE = 'Consignes de la copropriété';

const ilYA = (jours: number) => new Date(Date.now() - jours * 86400000).toISOString();

const ITEMS = [
	{
		id: 'pub-1',
		type: 'publication',
		date: ilYA(0),
		titre: 'Coupure d’eau jeudi',
		detail: 'De 9 h à 12 h',
		badges: [],
		icon: '📰',
		meta: {},
	},
	{
		id: 'pub-2',
		type: 'publication',
		date: ilYA(3),
		titre: 'Règles du local vélos',
		detail: 'À relire',
		badges: [],
		icon: '📰',
		meta: { epingle: true },
	},
	{
		id: 'pub-3',
		type: 'publication',
		date: ilYA(90),
		titre: 'Ravalement terminé',
		detail: 'Fin du chantier',
		badges: [],
		icon: '📰',
		meta: {},
	},
];

async function accueil(page: Page) {
	await simulerApi(page, (chemin) =>
		chemin === '/api/flux' ? { items: ITEMS, sante: {} } : undefined,
	);
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
}

test('le fil récent est groupé sous « Aujourd’hui »', async ({ page }) => {
	await accueil(page);
	await expect(page.locator('.flux-day-label', { hasText: "Aujourd'hui" })).toBeVisible();
	await expect(page.getByText('Coupure d’eau jeudi')).toBeVisible();
});

/**
 *  🗂️ La carte du fil est celle du site (10/10/2026, maquette B du fil) : la
 *  gouttière dit l'HEURE — le jour est l'intitulé du groupe — puis la rubrique,
 *  et le geste est asymétrique : un clic dans le corps déplié ne referme pas.
 */
test('la carte du fil a la gouttière du site : l’heure, puis la rubrique', async ({
	page,
}, info) => {
	await accueil(page);
	const carte = page.locator('.flux-groupes .carte-liste', { hasText: 'Coupure d’eau jeudi' });
	const heure = await page.evaluate(async (iso) => {
		const { fmtTime } = await import('/src/lib/date.ts');
		return fmtTime(iso);
	}, ITEMS[0].date);
	await expect(carte.locator('.gouttiere time')).toHaveText(heure);
	await expect(carte.locator('.gouttiere abbr')).toHaveText('ACTU.');
	if (info.project.name === 'bureau') {
		//  « 14:32 » tient dans la colonne, comme le jour d'une affaire.
		const deborde = await carte
			.locator('.gouttiere')
			.evaluate(
				(g) =>
					g.querySelector('.g-jour')!.getBoundingClientRect().right >
					g.getBoundingClientRect().right - 2,
			);
		expect(deborde, 'l’heure sort de la gouttière').toBe(false);
	}
	//  Le geste du site : repliée, toute la carte ouvre ; dépliée, le corps se lit.
	await carte.locator('.flux-detail').click();
	await expect(carte).toHaveClass(/expanded/);
	//  Dans un coin : le corps porte le lien vers l'écran d'origine.
	await carte.locator('.carte-corps').click({ position: { x: 4, y: 4 } });
	await expect(carte, 'un clic dans le corps a replié la carte').toHaveClass(/expanded/);
	await carte.locator('.ec-titre-btn').click();
	await expect(carte).not.toHaveClass(/expanded/);
});

/**
 *  Sans intitulé de jour, l'heure seule ne situait rien : la gouttière de
 *  l'épinglé dit la DATE (12/10/2026, signalé à l'écran).
 */
test('l’épinglé a son bandeau, sans intitulé de jour, et sa gouttière dit la date', async ({
	page,
}) => {
	await accueil(page);
	const bandeau = page.locator('.epingle-bloc');
	await expect(bandeau.getByText('Règles du local vélos')).toBeVisible();
	await expect(bandeau.locator('.flux-day-label')).toHaveCount(0);
	const date = await page.evaluate(async (iso) => {
		const { fmtDate } = await import('/src/lib/date.ts');
		return fmtDate(iso);
	}, ITEMS[1].date);
	const gouttiere = await bandeau
		.locator('.gouttiere time')
		.evaluate((t) => t.textContent!.replace(/\s+/g, ' ').trim());
	expect(gouttiere, 'la gouttière de l’épinglé ne dit pas le jour').toBe(date);
	//  Et il n'est pas lu deux fois : la chronologie ne le reprend pas.
	await expect(page.getByText('Règles du local vélos')).toHaveCount(1);
});

test('les Archives s’ouvrent et rendent leur carte, atténuée', async ({ page }) => {
	await accueil(page);
	await expect(page.getByText('Ravalement terminé')).toHaveCount(0);
	await page.getByRole('button', { name: /Archives/ }).click();
	await expect(page.getByText('Ravalement terminé')).toBeVisible();
	//  L'allure archivée de toute carte du site (`CarteListe archive`), plus un
	//  voile posé sur le groupe : c'est la carte qui s'atténue — par son FOND,
	//  jamais par l'opacité, qui retirait l'AA à chacun de ses textes (#2296).
	const allure = await page
		.locator('.carte-liste.attenue', { hasText: 'Ravalement terminé' })
		.evaluate((el) => {
			const s = getComputedStyle(el);
			const sonde = document.createElement('i');
			sonde.style.backgroundColor = 'var(--color-neutre-fond)';
			document.body.append(sonde);
			const neutre = getComputedStyle(sonde).backgroundColor;
			sonde.remove();
			return { opacite: s.opacity, fond: s.backgroundColor, neutre };
		});
	expect(allure.opacite).toBe('1');
	expect(allure.fond).toBe(allure.neutre);
});

test('l’accueil porte la pastille des consignes, vers la fiche', async ({ page }) => {
	await accueil(page);
	const lien = page.getByRole('link', { name: new RegExp(LIBELLE) });
	await expect(lien).toHaveAttribute('href', ADRESSE);
	await expect(lien).toHaveAttribute('target', '_blank');
});

test('l’annuaire dit la même chose, sous forme de bouton', async ({ page }) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/admin/annuaire'
			? {
					cs: { ag_annee: null, ag_date: null, membres: [] },
					syndic: { nom_syndic: '', adresse: '', site_web: null, membres: [] },
					whatsapp_url: null,
				}
			: undefined,
	);
	await page.goto('/annuaire');
	await attendreHydratation(page);
	const lien = page.getByRole('link', { name: LIBELLE });
	await expect(lien).toHaveAttribute('href', ADRESSE);
	await expect(lien).toHaveClass(/btn/);
});
