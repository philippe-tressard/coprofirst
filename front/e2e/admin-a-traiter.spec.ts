/*
 *  **Admin › À traiter : trois sections pliables, une seule ouverte (01/10/2026).**
 *
 *  Demandé : « regroupe en 3 sections pliables Comptes en attente, Commandes
 *  d'accès et Demandes profil ; Télémétrie, c'est plus de la gestion
 *  utilisateurs que de la configuration ». Ce test rend le VRAI écran, API
 *  simulée, et vérifie ce que l'administrateur voit : la pastille de l'onglet
 *  additionne les trois files, la première section qui a quelque chose à
 *  montrer s'ouvre seule, en ouvrir une autre la replie (accordéon), et la
 *  Télémétrie est rangée sous « Personnes » (groupes depuis #2062).
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const COMMANDES = [
	{ id: 1, user_id: 7, type: 'badge', lot_id: 12, cree_le: '2026-09-30T10:00:00' },
	{ id: 2, user_id: 8, type: 'télécommande', lot_id: 14, cree_le: '2026-09-30T11:00:00' },
];
const DEMANDES = [
	{
		id: 3,
		utilisateur_nom: 'Alice Dupont',
		utilisateur_email: 'alice@example.org',
		statut_actuel: 'locataire',
		statut_souhaite: 'copropriétaire_résident',
		cree_le: '2026-09-29T09:00:00',
	},
];

test('Admin › À traiter : trois sections en accordéon, Télémétrie en gestion', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/comptes-en-attente/enrichis') return [];
		if (chemin === '/api/admin/commandes-acces') return COMMANDES;
		if (chemin === '/api/admin/demandes-profil') return DEMANDES;
		return undefined;
	});
	await page.goto('/admin');

	const onglet = page.locator('.tab-btn', { hasText: 'À traiter' });
	await expect(onglet).toHaveClass(/active/);
	await expect(onglet.locator('.signal')).toHaveText('3');

	const entete = (titre: string) => page.locator('.sr-entete', { hasText: titre });
	//  Les comptes sont vides : c'est la section suivante, la première qui a
	//  quelque chose à montrer, qui s'ouvre.
	await expect(entete('Comptes en attente')).toHaveAttribute('aria-expanded', 'false');
	await expect(entete('Comptes en attente').locator('.compte')).toHaveText('0');
	await expect(entete("Commandes d'accès")).toHaveAttribute('aria-expanded', 'true');
	await expect(entete("Commandes d'accès").locator('.compte')).toHaveText('2');
	await expect(entete('Demandes de profil')).toHaveAttribute('aria-expanded', 'false');
	await expect(page.getByRole('cell', { name: '#7' })).toBeVisible();

	//  Accordéon : ouvrir les demandes replie les commandes.
	await entete('Demandes de profil').click();
	await expect(entete('Demandes de profil')).toHaveAttribute('aria-expanded', 'true');
	await expect(entete("Commandes d'accès")).toHaveAttribute('aria-expanded', 'false');
	await expect(page.getByText('Alice Dupont')).toBeVisible();
	await expect(page.getByRole('cell', { name: '#7' })).toHaveCount(0);

	//  Un second clic replie : plus rien d'ouvert.
	await entete('Demandes de profil').click();
	await expect(page.locator('.sr-entete[aria-expanded="true"]')).toHaveCount(0);

	//  Les anciens onglets ont disparu ; la Télémétrie est dans la rangée du
	//  groupe actif, « Personnes » (#2062).
	await expect(page.locator('.groupe[aria-current="true"]')).toContainText('Personnes');
	await expect(page.locator('.tab-btn', { hasText: 'Télémétrie' })).toHaveCount(1);
	for (const ancien of ['Comptes en attente', "Commandes d'accès", 'Demandes profil']) {
		await expect(page.locator('.tab-btn', { hasText: ancien })).toHaveCount(0);
	}

	//  Les onglets sont déclarés dans la table des pages (01/10/2026) : chacun est
	//  une adresse, et son descriptif s'affiche sous les rangées.
	await page.locator('.groupe', { hasText: 'Présentation' }).click();
	await page.locator('.tab-btn', { hasText: 'Modèles e-mail' }).click();
	await expect(page).toHaveURL(/\/admin\?onglet=emails$/);
	await expect(page.locator('.tab-descriptif')).toContainText('chaque courriel envoyé par le site');

	//  … et « Descriptif pages » les propose à la modification, comme ailleurs.
	await page.goto('/admin?onglet=pages');
	await page.locator('.page-row-btn', { hasText: 'Paramétrage' }).click();
	const cartes = page.locator('.onglet-card');
	//  19 depuis l'onglet « Installations » du registre (#1880) — et toujours 19
	//  après le rangement par niveau (#2062) : quatre partis, quatre venus.
	await expect(cartes).toHaveCount(19);
	await expect(cartes.first().locator('input').first()).toHaveValue('À traiter');

	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde).toBe(false);
});
