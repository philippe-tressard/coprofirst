/*
 *  **Le logo de la résidence se lit dans le menu.**
 *
 *  Demandé à l'écran le 08/10/2026, le logo une fois téléversé (#1728) : il
 *  s'affichait à 22 px, la taille d'une icône du menu. Un logo téléversé est
 *  une vignette pleine, et son dessin s'y réduisait à une tache. Il fait
 *  désormais 64 px sur la barre latérale et 30 dans l'en-tête mobile
 *  (`TAILLE_LOGO`, `MarqueResidence.svelte`), qui ne fait que 39 px de haut. Ce test passe
 *  sur les deux profils, mesure le logo que le profil AFFICHE, et vérifie qu'il
 *  tient dans sa barre : le lien mobile héritait du rembourrage de la barre
 *  latérale, et le logo en sortait par le haut.
 *
 *  À l'écran de connexion, le même logo se centre sous le titre (#2305) : il
 *  est un bloc, et `.auth-logo` le centrait par `text-align`, qu'un bloc ne
 *  suit pas — il restait collé au bord gauche de la carte.
 *
 *  Dans Admin › Copropriété › Identité, le logo et son dessin du fond sombre se
 *  règlent CÔTE À CÔTE (demandé à l'écran, 10/11/2026) : empilés, on ne les
 *  comparait pas d'un regard. Au téléphone ils retombent l'un sous l'autre.
 */
import { attendreHydratation, boiteStable, expect, MEMBRE_CS, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal } from './defilement';

test('le logo téléversé s’affiche en grand dans le menu, et tient dans sa barre', async ({
	page,
}, info) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/config' ? { site_nom: 'Résidence témoin', site_logo: 'logo.png' } : undefined,
	);
	await page.goto('/tableau-de-bord');
	//  Cas zéro : c'est bien le logo téléversé qui est rendu, pas l'icône.
	const logo = page.locator('.marque:visible img.logo-residence');
	await expect(logo).toHaveCount(1);
	const boite = await logo.boundingBox();
	const attendu = info.project.use.isMobile ? 30 : 64;
	expect(boite!.width).toBe(attendu);
	expect(boite!.height).toBe(attendu);
	if (info.project.use.isMobile) {
		const barre = (await page.locator('.mobile-topbar').boundingBox())!;
		expect(boite!.y, 'le logo sort de l’en-tête par le haut').toBeGreaterThanOrEqual(barre.y);
		expect(boite!.y + boite!.height, 'le logo sort de l’en-tête par le bas').toBeLessThanOrEqual(
			barre.y + barre.height,
		);
	}
});

test('à la connexion, le logo téléversé est centré sous le titre', async ({ page }) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/config' ? { site_nom: 'Résidence témoin', site_logo: 'logo.png' } : undefined,
	);
	await page.goto('/auth/connexion');
	//  Cas zéro : c'est bien le logo téléversé qui est rendu, pas l'icône.
	const logo = page.locator('.auth-logo img.logo-residence');
	await expect(logo).toHaveCount(1);
	const l = (await logo.boundingBox())!;
	const t = (await page.locator('.auth-header h1').boundingBox())!;
	const ecart = Math.abs(l.x + l.width / 2 - (t.x + t.width / 2));
	expect(ecart, 'le logo n’est pas centré sous le titre').toBeLessThanOrEqual(1);
});

test('en administration, les deux logos se règlent côte à côte, et s’empilent au téléphone @mise-en-page', async ({
	page,
}, info) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
		if (chemin === '/api/config' || chemin === '/api/config/admin')
			return { site_nom: 'Résidence témoin', site_logo: 'logo.png' };
	});
	await page.goto('/admin?onglet=copropriete');
	await attendreHydratation(page);
	const normal = page.locator('.field', { has: page.getByText('Logo sur fond normal') });
	const sombre = page.locator('.field', { has: page.getByText('Logo sur fond sombre') });
	//  Cas zéro : les deux champs sont rendus, chacun avec son geste.
	await expect(normal.getByRole('button', { name: 'Changer le logo' })).toBeVisible();
	await expect(sombre.getByRole('button', { name: 'Ajouter un logo' })).toBeVisible();
	const [n, s] = [await boiteStable(normal), await boiteStable(sombre)];
	if (info.project.use.isMobile) {
		expect(s.y, 'au téléphone, le fond sombre passe SOUS le fond normal').toBeGreaterThan(
			n.y + n.height - 1,
		);
	} else {
		expect(Math.abs(s.y - n.y), 'les deux logos ne sont pas sur la même ligne').toBeLessThanOrEqual(
			1,
		);
		expect(s.x, 'le fond sombre est à droite du fond normal').toBeGreaterThan(n.x + n.width - 1);
	}
	await attendreSansDefilementHorizontal(page);
});
