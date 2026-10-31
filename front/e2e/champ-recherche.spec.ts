/*
 *  **Le champ de RECHERCHE standard** (#2308, maquette B, 29/10/2026).
 *
 *  Demandé à l'écran : la saisie avait la couleur du fond de la page. Ce qu'on
 *  LIT, sur la page Affaires (le premier appelant de `ChampRecherche`) :
 *
 *  1. la saisie a le fond BLANC de la charte (`--color-surface`), distinct de
 *     la pierre de la page (`--color-bg`) ;
 *  2. la croix « Effacer la saisie » n'existe que si le champ a du texte, le
 *     vide et rend le focus au champ ;
 *  3. l'aide dit où l'on cherche, et elle est reliée au champ.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

test.beforeEach(async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/tickets' ? [] : undefined));
	await page.goto('/tickets');
	await attendreHydratation(page);
});

test('la saisie est blanche sur la pierre de la page', async ({ page }) => {
	const champ = page.getByRole('searchbox', { name: 'Recherche' });
	await expect(champ).toBeVisible();
	const fonds = await page.evaluate(() => {
		const cadre = document.querySelector('.recherche-cadre') as HTMLElement;
		const racine = getComputedStyle(document.documentElement);
		const teinte = (valeur: string) => {
			const t = document.createElement('div');
			t.style.backgroundColor = valeur;
			document.body.append(t);
			const c = getComputedStyle(t).backgroundColor;
			t.remove();
			return c;
		};
		return {
			cadre: getComputedStyle(cadre).backgroundColor,
			surface: teinte(racine.getPropertyValue('--color-surface')),
			page: teinte(racine.getPropertyValue('--color-bg')),
		};
	});
	expect(fonds.cadre).toBe(fonds.surface);
	expect(fonds.cadre).not.toBe(fonds.page);
});

test('la croix vide le champ et rend le focus', async ({ page }) => {
	const champ = page.getByRole('searchbox', { name: 'Recherche' });
	const effacer = page.getByRole('button', { name: 'Effacer la saisie' });
	await expect(effacer).toHaveCount(0);
	await champ.fill('ascenseur');
	await expect(effacer).toBeVisible();
	await effacer.click();
	await expect(champ).toHaveValue('');
	await expect(champ).toBeFocused();
	await expect(effacer).toHaveCount(0);
});

test("l'aide dit où l'on cherche, reliée au champ", async ({ page }) => {
	const champ = page.getByRole('searchbox', { name: 'Recherche' });
	await expect(champ).toHaveAccessibleDescription(
		/^Cherche dans : n°, titre.* —\u00a0sans tenir compte des accents ni des majuscules\.$/,
	);
});
