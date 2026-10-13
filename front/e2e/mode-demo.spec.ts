/*
 *  **La démo publique, à l'écran (#1906, spec `mode-demo.md` §8).**
 *
 *  `GET /config` dit `mode_demo` ; le reste suit de lui seul :
 *  - la connexion propose un LIEN par personnage — l'adresse d'entrée que sert la
 *    route — et ni formulaire, ni « Créer un compte », ni « Mot de passe oublié » ;
 *  - le bandeau « Démonstration » se lit sur la connexion ET dans l'application ;
 *  - hors démo, rien de cela : le formulaire est là, aucun bandeau.
 *
 *  API simulée : les personnages viennent du serveur, jamais recopiés à l'écran.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

const PERSONNAGES = [
	{ code: 'resident', libelle: 'Résident', description: 'Copropriétaire qui habite son lot.' },
	{ code: 'administrateur', libelle: 'Administrateur', description: 'Gestionnaire du site.' },
];

async function enDemo(page: import('@playwright/test').Page, demo: boolean) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/config') return { mode_demo: demo ? '1' : '0' };
		if (chemin === '/api/demo/personnages') return demo ? PERSONNAGES : [];
		return undefined;
	});
}

test('en démo, la connexion se fait par personnage, sans formulaire', async ({ page }) => {
	await enDemo(page, true);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	await expect(page.getByRole('note').filter({ hasText: 'Démonstration' })).toBeVisible();
	await expect(page.getByRole('link', { name: /Résident/ })).toHaveAttribute(
		'href',
		'/api/demo/entrer/resident',
	);
	await expect(page.getByRole('link', { name: /Administrateur/ })).toHaveAttribute(
		'href',
		'/api/demo/entrer/administrateur',
	);
	await expect(page.locator('form')).toHaveCount(0);
	await expect(page.getByRole('link', { name: 'Créer un compte' })).toHaveCount(0);
	await expect(page.getByRole('link', { name: 'Mot de passe oublié ?' })).toHaveCount(0);
});

test('hors démo, la connexion garde son formulaire et aucun bandeau', async ({ page }) => {
	await enDemo(page, false);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	await expect(page.locator('form input[type="email"]')).toBeVisible();
	await expect(page.getByRole('link', { name: 'Créer un compte' })).toBeVisible();
	await expect(page.getByRole('note').filter({ hasText: 'Démonstration' })).toHaveCount(0);
});

test('en démo, le bandeau se lit aussi dans l’application', async ({ page }) => {
	await enDemo(page, true);
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
	await expect(page.getByRole('note').filter({ hasText: 'Démonstration' })).toBeVisible();
});
