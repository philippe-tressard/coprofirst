/*
 *  **La page d'erreur est celle du site, en français** (#2304, 30/10/2026).
 *
 *  Le dépôt n'avait ni `routes/+error.svelte` ni `error.html` : une adresse
 *  inconnue rendait la page par défaut de SvelteKit — « 404 » puis « Not
 *  Found », en anglais, en haut à gauche, sans carte ni chemin de retour. Ce
 *  test la demande comme un visiteur la trouve (rendu du SERVEUR, adresse tapée
 *  ou lien ancien) et lit ce qu'elle dit, au clair puis au sombre, sur les deux
 *  profils.
 */
import { attendreLisible, forcerTheme } from './contraste-ecran';
import { attendreHydratation, expect, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal } from './defilement';

const ADRESSE_INCONNUE = '/page-qui-nexiste-pas';

test('une adresse inconnue rend la page d’erreur du site, en français, avec un retour', async ({
	page,
}) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/config' ? { site_nom: 'Résidence témoin' } : undefined,
	);
	const reponse = await page.goto(ADRESSE_INCONNUE);
	expect(reponse?.status(), 'le statut reste celui d’une page absente').toBe(404);
	await attendreHydratation(page);

	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Page introuvable');
	await expect(page).toHaveTitle(/^Page introuvable — /);
	await expect(page.locator('.auth-card')).toContainText(
		'Cette adresse ne correspond à aucune page',
	);
	//  Le message du framework ne paraît plus, nulle part.
	await expect(page.locator('body')).not.toContainText('Not Found');
	await expect(page.locator('html')).toHaveAttribute('lang', 'fr');

	//  Le chemin de retour : `/` trie (tableau de bord connecté, connexion sinon).
	const retour = page.getByRole('link', { name: 'Retour à l’accueil' });
	await expect(retour).toHaveAttribute('href', '/');
	//  Réessayer n'a de sens que si le serveur a échoué, pas pour une adresse absente.
	await expect(page.getByRole('button', { name: 'Réessayer' })).toHaveCount(0);
	await expect(page.locator('.code-erreur')).toHaveText('Résidence témoin · erreur 404');

	//  Rien ne déborde, au téléphone comme au bureau.
	await attendreSansDefilementHorizontal(page);
});

test('@sombre la page d’erreur se lit au sombre', async ({ page }) => {
	await simulerApi(page, () => undefined);
	await page.goto(ADRESSE_INCONNUE);
	await attendreHydratation(page);
	await forcerTheme(page, 'sombre');
	await attendreLisible(page);
});
