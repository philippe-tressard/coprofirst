/*
 *  **Un 401 ne veut pas dire la même chose partout.**
 *
 *  `messageErreur` traduit un 401 par « votre session a expiré — rechargez la
 *  page ». C'est juste pour tout appel d'API… sauf sur la mire : là, un 401
 *  signifie « identifiants refusés », et le serveur l'explique lui-même.
 *
 *  C'est la raison pour laquelle trois écrans d'authentification gardaient leur
 *  propre ternaire `e instanceof ApiError ? e.message : '…'` alors que le reste
 *  du produit passait au message partagé (#997) : le partager les aurait
 *  **dégradés**, en répondant « votre session a expiré » à qui venait de se
 *  tromper de mot de passe.
 *
 *  Depuis le 18/09/2026, `ApiError` porte le CHEMIN appelé et `messageErreur`
 *  s'appuie sur `CHEMINS_SANS_RENOUVELLEMENT` — la liste qui gouverne déjà le
 *  renouvellement de session. Une seule liste, deux usages.
 *
 *  ## Pourquoi un test de navigateur
 *
 *  Le produit n'a pas de banc de test unitaire côté TypeScript, et ce qui doit
 *  être tenu est ce que l'utilisateur LIT dans le bandeau. Un contrôle statique
 *  verrait que `messageErreur` est appelée ; il ne verrait pas la phrase.
 */
import { attendreHydratation, expect, test } from './aides';

const REFUS = 'Identifiants incorrects.';

test.describe('Le message d’un 401 dépend du chemin appelé', () => {
	test('un mot de passe refusé affiche la réponse du serveur, pas « session expirée »', async ({
		page,
	}) => {
		await page.route('**/api/auth/login', (route) =>
			route.fulfill({
				status: 401,
				contentType: 'application/json',
				body: JSON.stringify({ detail: REFUS }),
			}),
		);

		await page.goto('/auth/connexion');
		await attendreHydratation(page);
		await page.locator('#email').fill('quelquun@exemple.test');
		await page.locator('#password').fill('mauvais-mot-de-passe');
		await page.locator('button[type="submit"]').click();

		const bandeau = page.locator('.alert-error');
		await expect(bandeau).toContainText(REFUS);
		//  🔴 Le cœur du test : la phrase qui serait FAUSSE ici.
		await expect(bandeau).not.toContainText('session a expiré');
	});

	test('une panne réseau affiche le repli de l’écran, pas un message de session', async ({
		page,
	}) => {
		//  Ni `ApiError` ni statut : la requête n'aboutit pas. C'est le cas que le
		//  ternaire d'origine servait avec « Erreur de connexion », et que le
		//  paramètre de repli de `messageErreur` existe pour ne pas perdre.
		await page.route('**/api/auth/login', (route) => route.abort('connectionrefused'));

		await page.goto('/auth/connexion');
		await attendreHydratation(page);
		await page.locator('#email').fill('quelquun@exemple.test');
		await page.locator('#password').fill('peu-importe');
		await page.locator('button[type="submit"]').click();

		const bandeau = page.locator('.alert-error');
		await expect(bandeau).toContainText('Erreur de connexion');
		await expect(bandeau).not.toContainText('session a expiré');
	});
});
