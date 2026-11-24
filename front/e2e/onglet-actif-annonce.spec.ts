/*
 *  **L'onglet actif et l'entrée de menu active se DISENT, pas seulement se colorent** (#2943, 24/11/2026).
 *
 *  Une rangée d'onglets est une rangée de LIENS : chaque onglet est une adresse
 *  (`BarreOnglets`, arbitrage n° 38). Elle portait pourtant `role="tablist"`, sans
 *  un seul `role="tab"` dedans, et l'onglet actif ne se disait que par une classe —
 *  une couleur et un liseré, rien pour un lecteur d'écran (`standards/11` §2 :
 *  jamais une information par la seule couleur). Le menu, pareil.
 *
 *  La forme retenue est celle des liens de navigation : la rangée est un `<nav>`
 *  nommé, et le lien actif porte `aria-current="page"` — sur la rangée d'onglets,
 *  sur les sous-onglets des baux et sur le menu, au bureau comme au mobile.
 */
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

test('la rangée d’onglets est une navigation, et l’onglet actif se dit « page »', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await page.goto('/admin?onglet=utilisateurs');

	await expect(page.getByRole('tablist')).toHaveCount(0);
	const rangee = page.locator('nav.tabs');
	await expect(rangee).toHaveCount(1);
	await expect(rangee).toHaveAttribute('aria-label', /.+/);
	//  Un seul lien actif, et c'est celui que la couleur désigne.
	const actifs = rangee.locator('[aria-current="page"]');
	await expect(actifs).toHaveCount(1);
	await expect(actifs).toHaveText(/Utilisateurs/);
	await expect(actifs).toHaveClass(/\bactive\b/);
});

test('l’entrée de menu de la page ouverte se dit « page »', async ({ page, isMobile }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await page.goto('/admin?onglet=utilisateurs');
	await attendreHydratation(page);
	if (isMobile) await page.getByRole('button', { name: 'Menu' }).click();
	const menu = page.locator(isMobile ? '.overlay-menu' : 'nav.sidebar');
	const actifs = menu.locator('[aria-current="page"]');
	await expect(actifs).toHaveCount(1);
	await expect(actifs).toHaveClass(/\bactive\b/);
	await expect(actifs).toHaveAttribute('href', /^\/admin/);
});
