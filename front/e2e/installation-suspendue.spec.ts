/*
 *  **L'installation suspendue, à l'écran (R6 #1882, spec multi-copropriétés §4.11, D20).**
 *
 *  `GET /config` dit `installation_suspendue`, calculée par le serveur depuis le bail ;
 *  le bandeau « lecture seule » se lit sur la connexion ET dans l'application — avant
 *  qu'une écriture refusée l'apprenne à quelqu'un. Hors suspension, aucun bandeau.
 *
 *  Le texte rendu est EXACTEMENT celui que la release publie aux apps (`bandeauSuspendue`
 *  de `tables-clients.json`, #2840) : une copie réécrite dans le composant ferait diverger
 *  le site et les apps, et ce test le refuse.
 *
 *  API simulée.
 */
import { readFileSync } from 'node:fs';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const TABLES = JSON.parse(readFileSync(new URL('../tables-clients.json', import.meta.url), 'utf8'));
const PUBLIE = TABLES.tables.bandeauSuspendue.valeur;
const TIRET = TABLES.tables.separateurs.valeur.tiret;
/** Le bandeau tel que les apps le composent : titre, tiret, précision, point, texte. */
const TEXTE_PUBLIE = `${PUBLIE.titre}${TIRET}${PUBLIE.precision}. ${PUBLIE.texte}`;

async function suspendue(page: import('@playwright/test').Page, oui: boolean) {
	await simulerApi(page, (chemin) =>
		chemin === '/api/config' ? { installation_suspendue: oui ? '1' : '0' } : undefined,
	);
}

const BANDEAU = 'Installation suspendue';

test('suspendue, la connexion le dit et garde son formulaire', async ({ page }) => {
	await suspendue(page, true);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	const bandeau = page.getByRole('note').filter({ hasText: BANDEAU });
	await expect(bandeau).toBeVisible();
	//  Espaces normalisés des deux côtés : le rendu replie les retours à la ligne du gabarit.
	const rendu = (await bandeau.innerText()).replace(/\s+/g, ' ').trim();
	expect(rendu).toBe(TEXTE_PUBLIE.replace(/\s+/g, ' ').trim());
	await expect(page.locator('form input[type="email"]')).toBeVisible();
});

test('suspendue, le bandeau se lit aussi dans l’application', async ({ page }) => {
	await suspendue(page, true);
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
	await expect(page.getByRole('note').filter({ hasText: BANDEAU })).toBeVisible();
});

test('hors suspension, aucun bandeau', async ({ page }) => {
	await suspendue(page, false);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);
	await expect(page.locator('form input[type="email"]')).toBeVisible();
	await expect(page.getByRole('note').filter({ hasText: BANDEAU })).toHaveCount(0);
});
