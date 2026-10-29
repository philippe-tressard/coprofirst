/*
 *  **@sombre — la COQUE se lit au thème sombre** (mode sombre, #2174 — lot S4a).
 *
 *  La coque : navigation (barre, menu mobile, onglets et leurs groupes), en-tête
 *  de page, pied de page, modale, toasts, champs de formulaire, boutons, liens,
 *  focus et états désactivés. Chacun est rendu sous `data-theme="dark"` (la
 *  palette de S3, `styles/palette-sombre.css`) avec l'API simulée, et l'écran
 *  RENDU est relevé par `releverContrastes` : aucun texte sous l'AA, aucune
 *  surface claire oubliée. Le relevé lit les couleurs calculées — un composant
 *  qui lirait le mauvais jeton échoue ici, quel que soit le jeton.
 *
 *  ## Ce que le parcours a trouvé (29/10/2026)
 *
 *  Rien à corriger dans la coque : S0 à S3 avaient porté chaque couleur par son
 *  jeton. Le seul écart relevé à l'écran était au CLAIR — les initiales blanches
 *  de l'avatar sur le voile clair de l'en-tête d'accueil, 2,8:1 —, corrigé par
 *  #2296 : l'avatar y garde son aplat Bleu Seine. L'en-tête d'accueil est un
 *  dégradé : le relevé ne le mesure pas (`nonMesures`), il ne le compte pas conforme.
 *
 *  ## Ce qui reste aux autres zones de S4
 *
 *  Les écrans relevés ici montrent des listes VIDES : cartes, badges et kanban
 *  (S4b), tableaux et graphiques (S4c), éditeur riche et aperçus (S4d) ont leurs
 *  propres specs `@sombre`, sur le même relevé.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';
import { attendreLisible, forcerTheme, releverContrastes } from './contraste-ecran';

async function ouvrir(page: Page, chemin: string, moi: object = MEMBRE_CS) {
	await simulerApi(page, (c) => {
		if (c === '/api/auth/me') return moi;
		//  La démo publique pose son bandeau en tête de la colonne de contenu.
		if (c === '/api/config') return { mode_demo: '1' };
		return undefined;
	});
	await page.goto(chemin);
	await attendreHydratation(page);
	await forcerTheme(page, 'sombre');
}

/**
 *  Les classes COMMUNES de la coque, posées telles qu'un écran les écrit : elles
 *  vivent dans `src/styles/`, et aucun écran simulé ne les montre toutes à la
 *  fois (un bouton désactivé, un champ en lecture seule, un bouton icône pressé).
 */
const VITRINE = `<section class="card" id="vitrine-coque">
	<p><a href="#vitrine-coque">Un lien du texte</a></p>
	<p class="form-actions">
		<button type="button" class="btn btn-outline">Annuler</button>
		<button type="button" class="btn btn-primary">Enregistrer</button>
		<button type="button" class="btn btn-danger">Supprimer</button>
		<button type="button" class="btn btn-sm btn-outline">Petit</button>
		<button type="button" class="btn btn-primary" disabled>Indisponible</button>
	</p>
	<p>
		<button type="button" class="btn-icon" aria-label="Modifier">✎</button>
		<button type="button" class="btn-icon" aria-pressed="true" aria-label="Suite">↻</button>
		<button type="button" class="btn-icon-danger" aria-label="Retirer">✕</button>
	</p>
	<div class="field"><label for="vc-saisie">Champ</label><input id="vc-saisie" value="Une valeur" /></div>
	<div class="field"><label for="vc-lecture">Lecture seule</label><input id="vc-lecture" readonly value="Une valeur" /></div>
	<div class="field"><label for="vc-liste">Liste</label><select id="vc-liste"><option>Une option</option></select></div>
	<div class="field"><label for="vc-texte">Texte</label><textarea id="vc-texte">Un paragraphe</textarea></div>
	<p class="aide">Une phrase d’aide.</p>
</section>`;

test.describe('@sombre — la coque', () => {
	test('cas zéro : le relevé VOIT une surface claire et un texte illisible', async ({ page }) => {
		await ouvrir(page, '/tickets');
		await page.evaluate(() =>
			document
				.querySelector('main')!
				.insertAdjacentHTML(
					'afterbegin',
					'<p id="fautif" style="background: #ffffff; color: var(--color-text)">Écrit pour le clair</p>',
				),
		);
		const r = await releverContrastes(page, '#fautif');
		expect(r.surfacesClaires).toHaveLength(1);
		expect(r.contrastes).toHaveLength(1);
		//  … et au clair, le même élément n'a qu'un texte sombre sur blanc : rien à dire.
		await forcerTheme(page, 'clair');
		expect(await releverContrastes(page, '#fautif')).toMatchObject({
			contrastes: [],
			surfacesClaires: [],
		});
	});

	test('cas zéro des MARQUES : claire exprès, mais visible sur son fond', async ({ page }) => {
		await ouvrir(page, '/tickets');
		//  Deux barres posées sur la surface : l'une claire (`--color-primary`, la
		//  barre d'un graphique au sombre), l'autre de la couleur même du fond.
		await page.evaluate(() =>
			document
				.querySelector('main')!
				.insertAdjacentHTML(
					'afterbegin',
					'<div id="graphique" class="card"><b class="barre" style="display: block; height: 1rem; background: var(--color-primary)"></b><b class="barre" style="display: block; height: 1rem; background: var(--color-surface)"></b></div>',
				),
		);
		//  Sans l'option, la barre claire est une surface claire ; avec, elle est une
		//  marque, et seule la barre invisible sur son fond est refusée.
		expect((await releverContrastes(page, '#graphique')).surfacesClaires).toHaveLength(1);
		const r = await releverContrastes(page, '#graphique', { marques: '.barre' });
		expect(r.surfacesClaires).toEqual([]);
		expect(r.marques).toHaveLength(1);
		expect(r.marques[0]).toContain(': 1.00');
	});

	for (const [chemin, moi] of [
		['/tickets', MEMBRE_CS],
		['/profil', MEMBRE_CS],
		['/tableau-de-bord', MEMBRE_CS],
		['/admin?onglet=services', { ...MEMBRE_CS, role: 'admin', roles: ['admin'] }],
	] as const) {
		test(`navigation, en-tête, onglets et pied de page — ${chemin}`, async ({ page }) => {
			await ouvrir(page, chemin, moi);
			await attendreLisible(page);
		});
	}

	test('les classes communes : boutons, liens, champs, aide', async ({ page }) => {
		await ouvrir(page, '/profil');
		await page.evaluate(
			(h) => document.querySelector('main')!.insertAdjacentHTML('afterbegin', h),
			VITRINE,
		);
		await page.locator('#vc-saisie').focus();
		await attendreLisible(page, '#vitrine-coque');
	});

	test('le survol des boutons et de la navigation', async ({ page }, info) => {
		test.skip(info.project.name === 'mobile', 'au doigt, le survol n’existe pas');
		await ouvrir(page, '/profil');
		await page.evaluate(
			(h) => document.querySelector('main')!.insertAdjacentHTML('afterbegin', h),
			VITRINE,
		);
		const cibles = [
			page.locator('#vitrine-coque .btn-outline').first(),
			page.locator('#vitrine-coque .btn-primary').first(),
			page.locator('#vitrine-coque .btn-icon').first(),
			page.locator('nav .nav-item').first(),
		];
		for (const cible of cibles) {
			await cible.hover();
			await attendreLisible(page, '#vitrine-coque');
			await attendreLisible(page, 'nav');
		}
	});

	test('le formulaire de création ouvert : sections, étoiles, pied', async ({ page }) => {
		await ouvrir(page, '/tickets');
		await page
			.getByRole('button', { name: /Nouvelle affaire/ })
			.first()
			.click();
		await expect(page.locator('.formulaire-creation')).toBeVisible();
		await attendreLisible(page, '.formulaire-creation');
	});

	test('la modale de confirmation', async ({ page }) => {
		await ouvrir(page, '/tickets');
		await page.evaluate(async () => {
			const { confirmer } = await import('/src/lib/confirmation.ts');
			void confirmer({ titre: 'Retirer ?', message: 'Ce geste est définitif.', danger: true });
		});
		await expect(page.getByRole('dialog')).toBeVisible();
		await attendreLisible(page, '.modal');
	});

	test('les toasts : réussite, erreur, information', async ({ page }) => {
		await ouvrir(page, '/tickets');
		await page.evaluate(async () => {
			const { toast } = await import('/src/lib/components/Toast.svelte');
			toast('success', 'Enregistré.', 60000);
			toast('error', 'Échec de l’envoi.', 60000);
			toast('info', 'Pour information.', 60000);
		});
		await expect(page.locator('.toast')).toHaveCount(3);
		await attendreLisible(page, '.toast-container');
	});

	test('le menu mobile ouvert', async ({ page }, info) => {
		test.skip(info.project.name !== 'mobile', 'le menu ☰ n’existe qu’au téléphone');
		await ouvrir(page, '/tickets');
		await page.locator('button.hamburger').click();
		await expect(page.locator('button.hamburger')).toHaveAttribute('aria-expanded', 'true');
		await attendreLisible(page, '.overlay-menu');
	});
});
