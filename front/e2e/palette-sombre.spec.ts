/**
 *  La palette sombre s'allume là où elle doit, et NULLE PART AILLEURS
 *  (mode sombre, #2174 — lot S3).
 *
 *  ## Pourquoi un test de navigateur
 *
 *  `lint:palette-sombre` lit la palette dans la SOURCE. Ce qui est servi est
 *  autre chose : la copie « Auto » n'existe que dans la feuille construite
 *  (greffon `scripts/vite-palette-sombre.mjs`), et un sombre qui s'allumerait
 *  sans l'attribut qui le demande ne se voit que dans un navigateur au système
 *  sombre.
 *
 *  L'attribut est posé à la main : ce spec juge la FEUILLE. Qui pose
 *  l'attribut — le serveur, d'après le cookie du Profil — se juge dans
 *  `bascule-theme.spec.ts` (S5). L'écran de connexion est public et charge la
 *  feuille principale comme tout écran.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, test } from './aides';

const CLAIR = { fond: 'rgb(242, 239, 233)', texte: 'rgb(26, 26, 46)' }; // #f2efe9, #1a1a2e
const SOMBRE = { fond: 'rgb(13, 27, 42)', texte: 'rgb(232, 230, 225)' }; // #0d1b2a, #e8e6e1

/** Le fond et le texte de la page, et le `color-scheme` de la racine, pour un attribut. */
async function rendu(page: Page, theme: string | null) {
	return page.evaluate((valeur) => {
		const racine = document.documentElement;
		if (valeur === null) racine.removeAttribute('data-theme');
		else racine.setAttribute('data-theme', valeur);
		//  Le fond de la page est celui de la RACINE (`socle.css`) ; le texte, du corps.
		const style = getComputedStyle(racine);
		return {
			fond: style.backgroundColor,
			texte: getComputedStyle(document.body).color,
			schema: style.colorScheme,
		};
	}, theme);
}

async function ouvrir(page: Page, systeme: 'light' | 'dark') {
	await page.emulateMedia({ colorScheme: systeme });
	await page.goto('/auth/connexion');
	await attendreHydratation(page);
}

test.describe('La palette sombre', () => {
	test('sans l’attribut qui le demande, un système sombre reste au clair', async ({ page }) => {
		await ouvrir(page, 'dark');
		const r = await rendu(page, null);
		expect(r).toMatchObject(CLAIR);
		expect(r.schema, 'les contrôles natifs ne passent pas au sombre').not.toContain('dark');
		//  `light` ou une valeur inconnue : le clair aussi.
		expect(await rendu(page, 'light')).toMatchObject(CLAIR);
		expect(await rendu(page, 'autre')).toMatchObject(CLAIR);
	});

	test('forcé : `data-theme="dark"` allume la palette, même sur un système clair', async ({
		page,
	}) => {
		await ouvrir(page, 'light');
		const r = await rendu(page, 'dark');
		expect(r).toMatchObject(SOMBRE);
		expect(r.schema).toBe('dark');
	});

	test('Auto : la copie générée au build suit le système', async ({ page }) => {
		await ouvrir(page, 'dark');
		expect(await rendu(page, 'auto'), 'Auto + système sombre').toMatchObject(SOMBRE);
		await page.emulateMedia({ colorScheme: 'light' });
		expect(await rendu(page, 'auto'), 'Auto + système clair').toMatchObject(CLAIR);
	});

	test('l’impression garde la charte claire, même forcée au sombre', async ({ page }) => {
		await ouvrir(page, 'dark');
		await page.emulateMedia({ media: 'print' });
		expect(await rendu(page, 'dark')).toMatchObject(CLAIR);
	});

	test('les jetons neufs et les dérivés se résolvent dans les deux thèmes', async ({ page }) => {
		await ouvrir(page, 'light');
		const lire = (theme: string | null) =>
			page.evaluate((valeur) => {
				const racine = document.documentElement;
				if (valeur === null) racine.removeAttribute('data-theme');
				else racine.setAttribute('data-theme', valeur);
				const champ = document.querySelector('.field input');
				//  Un `color-mix` se sérialise `color(srgb …)` : le canevas le ramène en `rgb()`.
				const toile = document.createElement('canvas').getContext('2d')!;
				const sonde = (jeton: string) => {
					const i = document.createElement('i');
					i.style.color = `var(${jeton})`;
					document.body.append(i);
					toile.fillStyle = getComputedStyle(i).color;
					i.remove();
					toile.fillRect(0, 0, 1, 1);
					const [r, g, b] = toile.getImageData(0, 0, 1, 1).data;
					return `rgb(${r}, ${g}, ${b})`;
				};
				return {
					champ: champ ? getComputedStyle(champ).borderTopColor : null,
					surAccent: sonde('--color-sur-accent'),
					survolSucces: sonde('--color-success-plein-survol'),
					syndic: sonde('--kanban-syndic'),
				};
			}, theme);

		expect(await lire(null)).toEqual({
			champ: 'rgb(122, 136, 156)', //  #7a889c : la bordure d'un champ, à 3:1
			surAccent: 'rgb(26, 26, 46)',
			survolSucces: 'rgb(39, 106, 70)', //  l'aplat à 85 % sur noir
			syndic: 'rgb(245, 158, 11)', //  #f59e0b, par `--teinte-4`
		});
		//  La bordure d'un champ a une transition (`--duree-geste`) : on attend qu'elle se pose.
		await expect
			.poll(() => lire('dark'))
			.toEqual({
				champ: 'rgb(101, 128, 163)', //  #6580a3
				surAccent: 'rgb(26, 26, 46)', //  identique : texte sur l'or
				survolSucces: 'rgb(39, 106, 70)', //  dérivé de l'aplat sombre, inchangé
				syndic: 'rgb(245, 158, 11)', //  identique : la teinte tient 4,5 au sombre
			});
	});
});
