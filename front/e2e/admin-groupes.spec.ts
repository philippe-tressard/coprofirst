/*
 *  **Admin rangé par niveau : six groupes, deux rangées (#2062).**
 *
 *  Maquette validée le 21/10/2026 : la première rangée nomme les GROUPES, la
 *  seconde montre les onglets du groupe actif. Ce test rend le vrai écran, API
 *  simulée, sur les profils bureau ET mobile, et tient trois promesses :
 *
 *  1. chaque compte voit ses groupes et ses onglets, et rien d'autre —
 *     administrateur, administrateur + opérateur, opérateur seul ;
 *  2. CHAQUE adresse d'avant le rangement (`?onglet=<clé>`, liens de courriels
 *     et favoris) ouvre encore un onglet — et le bon, pour les clés retirées ;
 *  3. au doigt, les rangées ne font pas défiler la page et leurs cibles font
 *     44 px.
 */
import type { Page } from '@playwright/test';
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
const ADMIN_OPERATEUR = { ...MEMBRE_CS, role: 'admin', roles: ['admin', 'operateur'] };
const OPERATEUR_SEUL = { ...MEMBRE_CS, role: 'résident', roles: ['operateur', 'résident'] };

/**  Les dix-neuf clés d'onglet du 20/10/2026, avant le rangement. FIGÉES : elles
 *   vivent dans des courriels déjà envoyés, et la table du code a changé. */
const CLES_D_AVANT = [
	'a_traiter',
	'utilisateurs',
	'telemetry',
	'emails',
	'import_lots',
	'import_tc',
	'import_vigik',
	'audit_lots',
	'services',
	'site',
	'copropriete',
	'perimetres',
	'pages',
	'legal',
	'whatsapp',
	'smtp',
	'ia',
	'maintenance',
	'installations',
];

/** Les clés retirées, et ce qu'elles doivent ouvrir : onglet actif, source. */
const RETIREES: Record<string, { onglet: string; source?: string }> = {
	site: { onglet: 'Fonctionnement' },
	import_lots: { onglet: 'Imports', source: 'Lots' },
	import_tc: { onglet: 'Imports', source: 'Télécommandes' },
	import_vigik: { onglet: 'Imports', source: 'Vigik' },
};

async function ouvrir(page: Page, adresse: string, moi: object) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return moi;
		if (chemin === '/api/admin/installation')
			return { role: 'reference', libelle: 'Référence', branche: 'main', etat: 'non_verifie' };
		//  Le parcours ouvre chaque onglet : l'Assistant IA lit une LISTE d'usages.
		if (chemin === '/api/config/llm-usages') return [];
		return undefined;
	});
	await page.goto(adresse);
}

const groupes = (page: Page) => page.locator('nav.groupes .groupe');
const onglets = (page: Page) => page.locator('.tabs .tab-btn');

/** Les six groupes, dans l'ordre — le compte rouge peut suivre le nom. */
const SIX = [
	'👥 Personnes',
	'📥 Imports',
	'🏢 Copropriété',
	'🔌 Services',
	'🎨 Présentation',
	'🛠 Exploitation',
].map((nom) => new RegExp(`^ *${nom} *[0-9]* *$`));

test('administrateur : six groupes, l’Exploitation réduite à Maintenance', async ({ page }) => {
	await ouvrir(page, '/admin', ADMIN);
	await expect(page.locator('.groupe[aria-current="true"]')).toContainText('Personnes');
	await expect(groupes(page)).toHaveText(SIX);
	await expect(onglets(page)).toHaveText(['À traiter', 'Utilisateurs', 'Audit lots', 'Télémétrie']);

	//  Un groupe est un lien vers son premier onglet : la rangée suit.
	await groupes(page).filter({ hasText: 'Copropriété' }).click();
	await expect(page).toHaveURL(/\/admin\?onglet=copropriete$/);
	await expect(onglets(page)).toHaveText([
		'Identité',
		'Périmètres',
		'Équipements', // ce sur quoi l'on intervient, administrés (#2442)
		'Lots', // les lots selon le règlement (#2216)
		'Fonctionnement',
		'Pages légales',
	]);
	await groupes(page).filter({ hasText: 'Services' }).click();
	await expect(onglets(page)).toHaveText(['Services', 'Courriel', 'WhatsApp', 'Assistant IA']);
	await groupes(page).filter({ hasText: 'Présentation' }).click();
	await expect(onglets(page)).toHaveText([
		'Menu et pages',
		'Connexion et pied de page',
		'Modèles e-mail',
	]);
	//  L'Exploitation reste VISIBLE de l'administrateur : Maintenance lui est
	//  ouverte, Installation et Installations non (`reserve: 'operateur'`).
	await groupes(page).filter({ hasText: 'Exploitation' }).click();
	await expect(page).toHaveURL(/\/admin\?onglet=maintenance$/);
	await expect(onglets(page)).toHaveText(['Maintenance']);
});

test('administrateur + opérateur : l’Exploitation entière', async ({ page }) => {
	await ouvrir(page, '/admin?onglet=maintenance', ADMIN_OPERATEUR);
	await expect(groupes(page)).toHaveText(SIX);
	await expect(page.locator('.groupe[aria-current="true"]')).toContainText('Exploitation');
	await expect(onglets(page)).toHaveText(['Installation', 'Maintenance', 'Installations']);
	await expect(page.locator('.tab-btn.active')).toHaveText('Maintenance');
});

test('opérateur seul : un groupe, donc une seule rangée', async ({ page }) => {
	await ouvrir(page, '/admin', OPERATEUR_SEUL);
	await expect(onglets(page)).toHaveText(['Installation', 'Maintenance', 'Installations']);
	await expect(groupes(page)).toHaveCount(0);
});

test('chaque adresse d’avant le rangement ouvre un onglet, et le bon', async ({ page }) => {
	//  Dix-neuf ouvertures d'écran : le délai d'un test seul n'y suffit pas sur un
	//  poste chargé (rejeu du 21/10/2026).
	test.setTimeout(120_000);
	await ouvrir(page, '/admin', ADMIN_OPERATEUR);
	await expect(page.locator('.tab-btn.active')).toHaveText('À traiter');
	for (const cle of CLES_D_AVANT) {
		await page.goto(`/admin?onglet=${cle}`);
		const attendu = RETIREES[cle];
		if (attendu) {
			await expect(page.locator('.tab-btn.active'), cle).toHaveText(attendu.onglet);
			if (attendu.source)
				await expect(page.getByRole('radio', { name: attendu.source }), cle).toBeChecked();
		} else {
			//  Une clé conservée garde son adresse : la page ne l'a pas redirigée.
			await expect(page, cle).toHaveURL(new RegExp(`onglet=${cle}$|/admin$`));
			await expect(page.locator('.tab-btn.active'), cle).toHaveCount(1);
		}
	}
	//  Un courriel porte son étiquette de suivi (`src`) : la redirection ne la
	//  perd pas — la page la relève puis la retire de l'adresse (`#lib/arrivees`).
	await page.goto('/admin?onglet=import_tc&src=courriel:ticket_nouveau');
	await expect(page).toHaveURL(/onglet=imports&source=telecommandes/);
	await expect(page.getByRole('radio', { name: 'Télécommandes' })).toBeChecked();
});

test('au doigt : pas de défilement de page, cibles de 44 px', async ({ page, isMobile }) => {
	test.skip(!isMobile, 'mesure tactile : profil mobile seulement');
	await ouvrir(page, '/admin?onglet=services', ADMIN_OPERATEUR);
	await expect(onglets(page).first()).toBeVisible();
	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde).toBe(false);
	for (const cible of [groupes(page).first(), onglets(page).first()]) {
		const boite = await cible.boundingBox();
		expect(boite?.height ?? 0).toBeGreaterThanOrEqual(44);
	}
});
