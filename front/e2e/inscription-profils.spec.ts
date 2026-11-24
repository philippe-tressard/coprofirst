/*
 *  **Les profils de l'inscription, dans l'ordre et sous le nom de l'écran** (#2947, 24/11/2026).
 *
 *  La page recopiait six statuts et leurs libellés ; elle les lit désormais dans
 *  `#lib/roles` (`STATUTS_INSCRIPTION`, `LIBELLES_STATUT`). Ce test est le témoin
 *  que la dérivation n'a rien changé à l'écran : les mêmes six choix, le même
 *  ordre, les mêmes mots — et jamais le compte technique. Les libellés sont écrits
 *  ici exprès : c'est ce que la personne lit, pas une table à recopier.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

test('l’inscription propose les six profils, dans l’ordre de l’écran', async ({ page }) => {
	await simulerApi(page);
	await page.goto('/auth/inscription');
	await attendreHydratation(page);

	const choix = page.getByLabel(/Profil d'utilisateur/).locator('option');
	await expect(choix).toHaveText([
		'Copropriétaire résident',
		'Copropriétaire bailleur',
		'Locataire',
		'Syndic',
		'Mandataire',
		'Aidant (proche)',
	]);
	await expect(page.getByLabel(/Profil d'utilisateur/)).toHaveValue('copropriétaire_résident');
});
