/*
 *  **La saisie d'une affaire, Essentielle ou Complète** (#2595, arbitré le 08/11/2026).
 *
 *  Le même formulaire, montré de deux façons. En Essentielle, les sections que la
 *  catégorie n'appelle pas se rangent dans un groupe plié, « Plus de détails », en fin
 *  de formulaire ; en Complète, toutes sont à leur rang. Le mode est celui que l'API
 *  sert (`saisie_affaire_effective`) : l'écran le lit, il ne le dérive pas.
 *
 *  Ce test lit ce qu'on VOIT : le groupe plié, ce qu'il contient une fois ouvert, la
 *  phrase discrète qui renvoie au Profil, et le sélecteur du Profil qui enregistre.
 */
import type { Locator, Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ESSENTIELLE = { ...MEMBRE_CS, saisie_affaire: null, saisie_affaire_effective: 'essentielle' };
const COMPLETE = { ...MEMBRE_CS, saisie_affaire: null, saisie_affaire_effective: 'complete' };

/** Le titre d'une section du formulaire — rendue même pliée, ou cachée dans le groupe. */
const titre = (formulaire: Locator, nom: RegExp) =>
	formulaire.locator('.section-titre-texte', { hasText: nom });

async function nouvelleAffaire(page: Page, compte: object, categorie: RegExp): Promise<Locator> {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? compte : undefined));
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();
	await page.getByText(categorie).first().click();
	return page.getByRole('group', { name: /^Nouvelle affaire$/ });
}

const PANNE = /Ascenseur, chauffage, éclairage/;
const QUESTION = /Information, procédure/;

test('Essentielle : une panne montre le périmètre, la description et les pièces jointes', async ({
	page,
}) => {
	const f = await nouvelleAffaire(page, ESSENTIELLE, PANNE);
	for (const nom of [/^Périmètre/, /^Description/, /^Pièces jointes/]) {
		await expect(titre(f, nom).first()).toBeVisible();
	}
});

test('Essentielle : le reste est dans « Plus de détails », plié, et s’y déplie', async ({
	page,
}) => {
	const f = await nouvelleAffaire(page, ESSENTIELLE, PANNE);
	const groupe = f.getByRole('button', { name: /^Plus de détails \(\d+ sections?\)$/ });
	await expect(groupe).toBeVisible();
	await expect(groupe).toHaveAttribute('aria-expanded', 'false');
	for (const nom of [/^Équipement/, /^Suivi/, /^Affaires liées/, /^Diffusion/]) {
		await expect(titre(f, nom).first()).toBeHidden();
	}
	await groupe.click();
	await expect(groupe).toHaveAttribute('aria-expanded', 'true');
	for (const nom of [/^Équipement/, /^Suivi/, /^Affaires liées/, /^Diffusion/]) {
		await expect(titre(f, nom).first()).toBeVisible();
	}
});

test('Essentielle : une question ne garde que l’essentiel, sans pièces jointes', async ({
	page,
}) => {
	const f = await nouvelleAffaire(page, ESSENTIELLE, QUESTION);
	await expect(titre(f, /^Description/).first()).toBeVisible();
	await expect(titre(f, /^Pièces jointes/).first()).toBeHidden();
	await f.getByRole('button', { name: /^Plus de détails/ }).click();
	await expect(titre(f, /^Pièces jointes/).first()).toBeVisible();
});

test('Complète : toutes les sections sont à leur rang, sans groupe', async ({ page }) => {
	const f = await nouvelleAffaire(page, COMPLETE, PANNE);
	await expect(f.getByRole('button', { name: /^Plus de détails/ })).toHaveCount(0);
	for (const nom of [/^Équipement/, /^Suivi/, /^Périmètre/, /^Diffusion/]) {
		await expect(titre(f, nom).first()).toBeVisible();
	}
});

test('la phrase discrète dit le mode et renvoie au Profil', async ({ page }) => {
	const f = await nouvelleAffaire(page, ESSENTIELLE, PANNE);
	await expect(f.getByText(/Saisie essentielle/)).toBeVisible();
	const lien = f.getByRole('link', { name: /À changer dans votre profil/ });
	await expect(lien).toHaveAttribute('href', '/profil');
	await expect(lien).toHaveAttribute('target', '_blank');
});

test('le Profil enregistre le choix sur le compte et affiche le mode qui s’applique', async ({
	page,
}) => {
	const envois: unknown[] = [];
	let compte: Record<string, unknown> = { ...ESSENTIELLE };
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? compte : undefined));
	//  Enregistrée APRÈS : Playwright essaie la dernière route d'abord.
	await page.route(
		(url) => url.pathname === '/api/auth/me',
		(route) => {
			if (route.request().method() !== 'PATCH') return route.fallback();
			const corps = route.request().postDataJSON() as { saisie_affaire?: string };
			envois.push(corps);
			compte = {
				...compte,
				saisie_affaire: corps.saisie_affaire === 'role' ? null : corps.saisie_affaire,
				saisie_affaire_effective:
					corps.saisie_affaire === 'role' ? 'complete' : corps.saisie_affaire,
			};
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify(compte),
			});
		},
	);
	await page.goto('/profil');
	await attendreHydratation(page);

	const carte = page.locator('section', { hasText: /Saisie d’une affaire/ });
	await expect(carte.getByText(/Saisie essentielle aujourd’hui/)).toBeVisible();
	await carte.getByRole('radio', { name: /^Complète/ }).check({ force: true });

	await expect.poll(() => envois).toEqual([{ saisie_affaire: 'complete' }]);
	await expect(carte.getByText(/Saisie complète aujourd’hui/)).toBeVisible();
});
