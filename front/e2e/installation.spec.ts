/*
 *  **L'administration dit le rôle de l'installation** (#1761, exigence du 08/10/2026 :
 *  « savoir si l'instance est le master (git => main) ou une réplique »).
 *
 *  Le VRAI onglet Maintenance, API simulée, trois cas que l'écran ne doit pas
 *  confondre :
 *  - la référence, service coupé : « Référence — suit main », et « Non vérifié »,
 *    jamais « À jour » — avec où s'active la vérification ;
 *  - une réplique en retard : le retard se dit, sur `replica` ;
 *  - un rôle non déclaré : « Inconnu », jamais « Référence », et ce qu'il manque.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

//  La supervision technique est à l'OPÉRATEUR de la plateforme (#1750).
const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin', 'operateur'] };

const BASE = {
	empreinte: '79ce8c5b',
	demarree_le: '2026-10-09T00:25:00',
	retard: 0,
};

async function ouvrir(page, installation, inscription?: unknown) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/installation') return installation;
		if (chemin === '/api/admin/installation/inscription') return inscription;
		return undefined;
	});
	await page.goto('/admin?onglet=installation');
	const carte = page.locator('section.config-section', {
		has: page.getByText('Installation', { exact: true }),
	});
	await expect(carte).toBeVisible();
	return carte;
}

test('Installation : la référence, vérification coupée, ne se dit jamais « à jour »', async ({
	page,
}) => {
	const carte = await ouvrir(page, {
		...BASE,
		role: 'reference',
		libelle: 'Référence',
		branche: 'main',
		verification_active: false,
		etat: 'non_verifie',
		detail: 'service « Vérification de la version » coupé',
	});
	await expect(carte.getByText('Référence', { exact: true })).toBeVisible();
	await expect(carte.locator('code', { hasText: /^main$/ })).toBeVisible();
	await expect(carte.getByText(/Non vérifié — service/)).toBeVisible();
	await expect(carte.getByText(/À jour sur/)).toHaveCount(0);
	await expect(carte.getByText(/s’active dans Administration › Services/)).toBeVisible();
	await expect(carte.locator('a', { hasText: '79ce8c5b' })).toHaveAttribute(
		'href',
		/\/tree\/79ce8c5b$/,
	);
	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'défilement horizontal dans l’onglet Maintenance').toBe(false);
	await carte.screenshot({ path: `test-results/installation-${test.info().project.name}.png` });
});

test('Installation : une réplique en retard le dit, sur replica', async ({ page }) => {
	const carte = await ouvrir(page, {
		...BASE,
		role: 'replique',
		libelle: 'Réplique',
		branche: 'replica',
		verification_active: true,
		etat: 'en_retard',
		retard: 3,
		detail: '',
	});
	await expect(carte.getByText('Réplique', { exact: true })).toBeVisible();
	await expect(carte.getByText('3 commit(s) de retard sur replica')).toBeVisible();
	await expect(carte.getByText(/s’active dans/)).toHaveCount(0);
});

test('Installation : un rôle non déclaré est « Inconnu », jamais « Référence »', async ({
	page,
}) => {
	const carte = await ouvrir(page, {
		...BASE,
		role: 'inconnu',
		libelle: 'Inconnu',
		branche: null,
		verification_active: false,
		etat: 'non_verifie',
		detail: 'rôle non déclaré : ROLE_INSTALLATION absent ou mal écrit',
	});
	await expect(carte.getByText('Inconnu', { exact: true })).toBeVisible();
	await expect(carte.getByText('Référence', { exact: true })).toHaveCount(0);
	await expect(carte.getByText(/n’est pas déclaré dans le/)).toBeVisible();
});

test('Maintenance : un administrateur qui n’est pas opérateur ne voit pas la supervision', async ({
	page,
}) => {
	//  #1750 : l'administrateur de copropriété garde ce qui porte des données de la
	//  résidence ; la supervision technique est à l'opérateur, et la page le dit.
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return { ...ADMIN, roles: ['admin'] };
		return undefined;
	});
	await page.goto('/admin?onglet=maintenance');
	await expect(
		page.getByText("réservée à l'opérateur de la plateforme", { exact: false }),
	).toBeVisible();
	await expect(page.getByText('Installation', { exact: true })).toHaveCount(0);
	await expect(page.getByText('Contrôles de fiabilité', { exact: true })).toHaveCount(0);
});

// ── Inscription au registre (R2 #1878) ─────────────────────────────────────

const REPLIQUE = {
	...BASE,
	role: 'replique',
	libelle: 'Réplique',
	branche: 'replica',
	verification_active: false,
	etat: 'non_verifie',
	detail: 'service « Vérification de la version » coupé',
};

test('Inscription : une réplique non inscrite s’inscrit en acceptant les conditions lues', async ({
	page,
}) => {
	const carte = await ouvrir(page, REPLIQUE);
	let envoye: Record<string, unknown> | null = null;
	await page.route(
		(url) => url.pathname === '/api/admin/installation/conditions',
		(route) =>
			route.fulfill({
				json: { version: 1, empreinte: 'a'.repeat(64), texte: 'Article 1 — Engagements.' },
			}),
	);
	await page.route(
		(url) => url.pathname === '/api/admin/installation/inscription',
		(route) => {
			if (route.request().method() !== 'POST') return route.fallback();
			envoye = route.request().postDataJSON();
			return route.fulfill({
				json: {
					etat: 'limitee',
					raison: 'inscription en attente de validation par la référence',
					identifiant: 'CF-000007',
					canal: null,
					version_cible: null,
					echeance: null,
					renouvellement_en_retard: false,
					inscrite_le: '2026-10-13T10:00:00',
					dernier_renouvellement_le: null,
					derniere_erreur: null,
					contact: { prenom: 'Alix', nom: 'Durand', courriel: 'alix@example.org' },
					conditions_acceptees: 1,
					conditions_en_vigueur: 1,
					peut_s_inscrire: true,
					essai_refuse: false,
					registre_url: 'https://registre.example',
				},
			});
		},
	);
	await expect(carte.getByText(/installation non inscrite au registre/)).toBeVisible();
	await expect(carte.getByText(/Constaté seulement/)).toBeVisible();
	await carte.getByRole('button', { name: 'Inscrire l’installation' }).click();

	const enregistrer = carte.getByRole('button', { name: 'Enregistrer' });
	await carte.locator('#ins-prenom').fill('Alix');
	await carte.locator('#ins-nom').fill('Durand');
	await carte.locator('#ins-courriel').fill('alix@example.org');
	//  Le texte se LIT, mis en forme, dans une boîte qui défile (#1930) — plus une zone de saisie.
	await expect(
		carte.getByRole('region', { name: /Conditions d’inscription, version 1/ }),
	).toContainText('Article 1 — Engagements.');
	//  Pas d'engagement sur un texte qu'on n'a pas accepté.
	await expect(enregistrer).toBeDisabled();
	await carte.getByLabel(/J’accepte les conditions d’inscription/).check();
	await enregistrer.click();

	await expect(carte.getByText('CF-000007')).toBeVisible();
	await expect(carte.getByText(/en attente de validation/)).toBeVisible();
	expect(envoye).toMatchObject({ conditions_acceptees: 1, accepte: true, prenom: 'Alix' });
	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'défilement horizontal dans la carte Installation').toBe(false);
	await carte.screenshot({ path: `test-results/inscription-${test.info().project.name}.png` });
});

test('Inscription : la référence n’est jamais limitée et ne s’inscrit pas', async ({ page }) => {
	const carte = await ouvrir(
		page,
		{ ...REPLIQUE, role: 'reference', libelle: 'Référence' },
		{
			etat: 'reference',
			raison: 'la référence n’est jamais limitée',
			identifiant: null,
			canal: null,
			version_cible: null,
			echeance: null,
			renouvellement_en_retard: false,
			inscrite_le: null,
			dernier_renouvellement_le: null,
			derniere_erreur: null,
			contact: null,
			conditions_acceptees: null,
			conditions_en_vigueur: 1,
			peut_s_inscrire: false,
			essai_refuse: false,
			registre_url: 'https://registre.example',
		},
	);
	await expect(carte.getByText(/la référence n’est jamais limitée/)).toBeVisible();
	await expect(carte.getByRole('button', { name: 'Inscrire l’installation' })).toHaveCount(0);
});
