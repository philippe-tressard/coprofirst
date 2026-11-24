/*
 *  **Ce qui dépend du rôle se charge aussi par un lien direct** (#1486, 30/09/2026).
 *
 *  Svelte monte la page avant le layout : l'`onMount` d'un écran précède celui
 *  qui charge l'utilisateur, et y lisait `false` / `null` sur un chargement
 *  direct ou un rechargement. Seule une navigation interne rendait l'écran juste,
 *  et c'est la seule que les tests faisaient.
 *
 *  Un cas par écran corrigé : chaque `page.goto` est un chargement DIRECT, et
 *  chacun échouait avant `quandAuthResolue`. `mon-lot` a le sien dans
 *  `lots-bailleur.spec.ts`. 🔒 `npm run lint:gardes-auth` refuse la récidive.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

/** Rend `chemin` avec `moi` pour utilisateur, et relève les appels à l'API. */
async function ouvrir(
	page: Page,
	chemin: string,
	moi: object,
	reponses: (chemin: string) => unknown = () => undefined,
) {
	const appels: string[] = [];
	await simulerApi(page, (c) => {
		appels.push(c);
		if (c === '/api/auth/me') return moi;
		return reponses(c);
	});
	await page.goto(chemin);
	await attendreHydratation(page);
	return appels;
}

test('délégations : le CS reçoit la liste des résidents délégables', async ({ page }) => {
	const appels = await ouvrir(page, '/delegations', MEMBRE_CS);
	await expect.poll(() => appels).toContain('/api/admin/utilisateurs');
});

test('fiche d’un sondage : un gestionnaire est renvoyé au tableau de bord', async ({ page }) => {
	const SYNDIC = { ...MEMBRE_CS, statut: 'syndic', role: 'externe', roles: ['externe'] };
	await ouvrir(page, '/sondages/1', SYNDIC, (c) =>
		c === '/api/sondages/1' ? { id: 1, question: 'Témoin', options: [] } : undefined,
	);
	await expect(page).toHaveURL(/\/tableau-de-bord/);
});

test('badges : un locataire reçoit les accès remis par son bailleur', async ({ page }) => {
	const LOCATAIRE = { ...MEMBRE_CS, statut: 'locataire', role: 'résident', roles: ['résident'] };
	const appels = await ouvrir(page, '/mon-lot/badges', LOCATAIRE);
	await expect.poll(() => appels).toContain('/api/bailleur/mes-acces-recus');
});

test('profil : le refus de la télémétrie est coché s’il a été posé', async ({ page }) => {
	await ouvrir(page, '/profil', { ...MEMBRE_CS, opt_out_telemetrie: true });
	await expect(
		page.getByRole('checkbox', { name: /Refuser la collecte de statistiques/ }),
	).toBeChecked();
});
