/*
 *  **Le suivi optionnel d'une actualité** (10/10/2026).
 *
 *  Demandé : *« une affaire de type actualité possède un suivi (optionnel) à
 *  trois états seulement, activable uniquement par le CS : Ouvert (par défaut),
 *  Résolu ou Annulé »*. Arbitré : une case « Activer le suivi » au formulaire,
 *  puis l'état par une Suite.
 *
 *  La règle du serveur est tenue par `api/tests/test_suivi_actualite.py` ; ce
 *  test tient l'écran : la case part dans le corps, la carte montre l'état, et
 *  la Suite ne propose que les trois états — jamais ceux d'une affaire.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

const ACTUALITE = {
	id: 51,
	numero: 'TK-A00051',
	titre: 'Coupure d’eau jeudi',
	description: 'De 8 h à 12 h.',
	categorie: 'actualite',
	statut: 'publie',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	public_cible: [],
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	natures: ['actualite'],
	suivi_actualite: null as string | null,
	cree_le: '2026-10-08T10:00:00',
	mis_a_jour_le: '2026-10-08T10:00:00',
};

test('le conseil active le suivi d’une actualité en la corrigeant', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [ACTUALITE];
		if (chemin === '/api/tickets/51') return ACTUALITE;
	});
	let corps: Record<string, unknown> | null = null;
	//  Enregistrée APRÈS : Playwright essaie la dernière route d'abord.
	await page.route(
		(url) => url.pathname === '/api/tickets/51',
		(route) => {
			if (route.request().method() !== 'PATCH') return route.fallback();
			corps = route.request().postDataJSON();
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({ ...ACTUALITE, suivi_actualite: 'ouvert' }),
			});
		},
	);
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: 'Modifier', exact: true }).first().click();

	//  Facultatif, le Suivi d'une actualité est plié : on l'ouvre, puis on coche.
	const caseSuivi = page.getByRole('checkbox', { name: 'Activer le suivi' });
	await expect(caseSuivi).toHaveCount(0);
	await page
		.locator('.section-titre-texte', { hasText: /^Suivi/ })
		.first()
		.click();
	await caseSuivi.check();
	//  Cochée : l'état part en « Ouvert », et se choisit d'un clic.
	await expect(page.getByRole('button', { name: /Ouvert/ }).first()).toBeVisible();

	//  Choisi dès l'ouverture : une résolution rapide s'enregistre « Résolu » (10/10/2026).
	await page
		.getByRole('button', { name: /Résolu/ })
		.first()
		.click();

	await page.getByRole('button', { name: 'Enregistrer', exact: true }).first().click();
	await expect.poll(() => corps).not.toBeNull();
	expect(corps).toMatchObject({
		categorie: 'actualite',
		suivre_actualite: true,
		suivi_actualite: 'résolu',
	});
});

test('une actualité suivie montre son état, et sa Suite ne propose que trois états', async ({
	page,
}) => {
	//  L'état du suivi en clair est SERVI (`suivi_actualite_libelle`, #2633).
	const suivie = { ...ACTUALITE, suivi_actualite: 'ouvert', suivi_actualite_libelle: 'Ouvert' };
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [suivie];
		if (chemin === '/api/tickets/51') return suivie;
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	await expect(page.locator('.carte-liste .badge', { hasText: 'Ouvert' }).first()).toBeVisible();

	await page.getByRole('button', { name: 'Ajouter une suite', exact: true }).first().click();
	const suivi = page.locator('.section-formulaire', {
		has: page.locator('.section-titre-texte', { hasText: /^Suivi/ }),
	});
	for (const etat of ['Ouvert', 'Résolu', 'Annulé']) {
		await expect(suivi.getByRole('button', { name: new RegExp(etat) })).toHaveCount(1);
	}
	await expect(suivi.getByRole('button', { name: /En cours|En AG|prestataire/ })).toHaveCount(0);
});
