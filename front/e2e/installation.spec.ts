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

async function ouvrir(page, installation) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/installation') return installation;
		return undefined;
	});
	await page.goto('/admin?onglet=maintenance');
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

test('Installation : un rôle non déclaré est « Inconnu », jamais « Référence »', async ({ page }) => {
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
