/*
 *  **L'annuaire de l'espace CS — conseil syndical et syndic.**
 *
 *  Extrait de `espace-cs/+page.svelte` le 29/09/2026 (#779, modularité) :
 *  `AnnuaireConseil`, `AnnuaireSyndic`, et les rapprochements par le nom dans
 *  `#lib/annuaire-rapprochement`. Un découpage ne change pas un comportement —
 *  ce test le vérifie sur le VRAI écran, API simulée :
 *
 *  • les deux sections s'amorcent seules et rendent leurs membres, avec les
 *    pastilles de rôle HABILLÉES (leur style a changé de fichier : une pastille
 *    nue ne lèverait rien, v2.67.11) ;
 *  • un NOM saisi lie le membre à un inscrit et le localise par le registre
 *    importé, et c'est ce qui PART au serveur ;
 *  • le syndic refuse un membre sans téléphone, sans rien envoyer.
 *
 *  Depuis le 02/10/2026 (#1539), les deux listes passent par `AnnuaireMembres`,
 *  qui RELAIE les emplacements de `CarteMembre`. D'où trois cas de plus, sur ce
 *  qu'une factorisation perd sans un mot : le détail propre du conseil (un
 *  emplacement relayé paraît toujours rempli), l'ordre du syndic et son
 *  interlocuteur principal, et l'en-tête qui envoie la liste entière.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const CS = {
	ag_annee: 2025,
	ag_date: '2025-06-12',
	whatsapp_url: '',
	//  La forme RÉELLE de `membres_du_conseil(pour_administration=True)` —
	//  identifiant compris : c'est lui qui fait réconcilier le PUT (#1680).
	membres: [
		{
			id: 31,
			genre: 'Mme',
			prenom: 'Anne',
			nom: 'Durand',
			batiment_id: 2,
			batiment_nom: '2',
			etage: 3,
			est_gestionnaire_site: false,
			est_president: true,
			photo_url: null,
			ordre: 0,
			user_id: null,
		},
	],
};
const SYNDIC = {
	nom_syndic: 'Cabinet Exemple',
	nom_syndic_source: 'saisie',
	membres: [
		{
			genre: 'M.',
			prenom: 'Paul',
			nom: 'Martin',
			fonction: 'Gestionnaire',
			telephone: '0102030405',
			est_principal: true,
		},
	],
};
const INSCRITS = [
	{ id: 42, prenom: 'Luc', nom: 'Bernard', email: 'l@b.fr', telephone: null, batiment_id: 4 },
];
const LOTS = [
	{ id: 9, numero: '41', type: 'appartement', etage: 1, batiment_id: 4, batiment_nom: 'Bât. 4' },
];
const IMPORTS = [
	{ nom_coproprietaire: 'BERNARD Luc', type_raw: 'AP', etage_raw: '1ER', lot_id: 9 },
];

//  Ce que l'écran envoie, tel que les assertions le lisent.
type Envoi = { chemin: string; corps: { membres: { id?: number; nom: string }[] } };

async function ouvrir(page: Page, syndic: typeof SYNDIC = SYNDIC): Promise<Envoi[]> {
	const envois: Envoi[] = [];
	page.on('request', (r) => {
		const chemin = new URL(r.url()).pathname;
		if (r.method() === 'PUT' && chemin.startsWith('/api/'))
			envois.push({ chemin, corps: r.postDataJSON() });
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/admin/annuaire/cs') return CS;
		if (chemin === '/api/admin/annuaire/syndic') return syndic;
		if (chemin === '/api/admin/utilisateurs') return INSCRITS;
		if (chemin === '/api/lots/admin/tous') return LOTS;
		if (chemin === '/api/lots/admin/imports') return IMPORTS;
		if (chemin === '/api/auth/batiments') return [{ id: 4, numero: '4' }];
	});
	await page.goto('/espace-cs/annuaire');
	await attendreHydratation(page);
	return envois;
}

const section = (page: Page, titre: string) =>
	page.locator('section.annuaire-section', {
		has: page.getByRole('heading', { name: titre, exact: true }),
	});

test('les deux sections rendent leurs membres, pastilles de rôle habillées', async ({ page }) => {
	await ouvrir(page);
	const conseil = section(page, 'Conseil Syndical');
	await expect(conseil).toContainText('AG 2025');
	await expect(conseil).toContainText('DURAND');
	const president = conseil.locator('.summary-role-badge-president');
	await expect(president).toHaveText(/Président/);
	//  Habillée : fond de la teinte d'avertissement, pas le transparent d'une classe nue.
	await expect(president).toHaveCSS('background-color', 'rgb(253, 243, 224)');

	const syndic = section(page, 'Syndic');
	await expect(syndic).toContainText('MARTIN');
	await expect(syndic.locator('.summary-role-badge-principal')).toHaveText(
		/Interlocuteur principal/,
	);
	await expect(syndic.locator('.summary-fonction')).toHaveText('Gestionnaire');
});

test('un nom saisi lie l’inscrit, localise le membre, et c’est ce qui part', async ({ page }) => {
	const envois = await ouvrir(page);
	const conseil = section(page, 'Conseil Syndical');
	await conseil.getByRole('button', { name: /Nouveau membre CS/ }).click();
	const nom = conseil.getByPlaceholder('NOM', { exact: true });
	await nom.fill('Bernard');
	await nom.dispatchEvent('input');
	await expect(conseil.locator('.localisation-info')).toContainText('1');
	await expect(conseil.getByText(/Inscrit lié/).first()).toBeVisible();

	await conseil.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0].chemin).toBe('/api/admin/annuaire/cs');
	const ajoute = envois[0].corps.membres.find((m) => m.nom === 'Bernard');
	expect(ajoute).toMatchObject({ user_id: 42, batiment_id: 4, batiment_nom: '4', etage: 1 });
});

test('le syndic refuse un membre sans téléphone, et n’envoie rien', async ({ page }) => {
	const envois = await ouvrir(page);
	const syndic = section(page, 'Syndic');
	await syndic.getByRole('button', { name: /Nouveau membre Syndic/ }).click();
	await syndic.getByPlaceholder('NOM', { exact: true }).fill('Petit');
	await syndic.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	await expect(page.getByText('Au moins un téléphone requis')).toBeVisible();
	expect(envois).toHaveLength(0);
});

test('les téléphones du syndic s’éditent sans perdre le focus, et le retrait ôte la bonne ligne', async ({
	page,
}) => {
	//  La boucle est clée par l'INDEX (`lint:each-key`, #1571) : une clé tirée de la
	//  valeur recréerait le champ à chaque caractère, et le focus partirait.
	await ouvrir(page);
	const syndic = section(page, 'Syndic');
	await syndic.getByRole('button', { name: /Nouveau membre Syndic/ }).click();
	const champs = syndic.getByPlaceholder('ex. 01 23 45 67 89');
	await champs.first().click();
	await page.keyboard.type('0612345678');
	await expect(champs.first()).toBeFocused();
	await expect(champs.first()).toHaveValue('0612345678');

	await syndic.getByRole('button', { name: '+ N° de téléphone' }).click();
	await champs.nth(1).fill('0700000000');
	await expect(champs).toHaveCount(2);
	await syndic.getByRole('button', { name: 'Retirer ce numéro' }).first().click();
	await expect(champs).toHaveCount(1);
	await expect(champs.first()).toHaveValue('0700000000');
});

test('déplié, le conseil montre son détail et le syndic son résumé', async ({ page }) => {
	await ouvrir(page);
	const conseil = section(page, 'Conseil Syndical');
	await conseil.getByRole('button', { name: /DURAND/ }).click();
	await expect(conseil.locator('.localisation-info')).toHaveCount(1);
	await expect(conseil.locator('.membre-summary')).toHaveCount(0);

	const syndic = section(page, 'Syndic');
	await syndic.getByRole('button', { name: /MARTIN/ }).click();
	await expect(syndic.locator('.membre-summary .summary-fonction')).toHaveText('Gestionnaire');
});

test('le syndic se réordonne, l’ordre part au serveur, un seul principal', async ({ page }) => {
	const morel = { ...SYNDIC.membres[0], prenom: 'Zoé', nom: 'Morel', est_principal: false };
	const envois = await ouvrir(page, { ...SYNDIC, membres: [...SYNDIC.membres, morel] });
	const syndic = section(page, 'Syndic');
	await syndic.getByRole('button', { name: 'Descendre' }).first().click();
	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0].corps.membres.map((m) => m.nom)).toEqual(['Morel', 'Martin']);
	//  Pas de « Monter » en tête ; « principal » se propose au seul membre qui ne l'est pas.
	await expect(syndic.getByRole('button', { name: 'Monter' })).toHaveCount(1);
	await expect(syndic.getByRole('button', { name: 'Définir interlocuteur principal' })).toHaveCount(
		1,
	);
});

test('l’en-tête du conseil s’enregistre avec la liste entière', async ({ page }) => {
	const envois = await ouvrir(page);
	const conseil = section(page, 'Conseil Syndical');
	await conseil.locator('.header-summary').getByRole('button', { name: 'Modifier' }).click();
	await conseil.getByLabel('Voté en AG').fill('2026');
	await conseil.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0].corps).toMatchObject({ ag_annee: 2026 });
	expect(envois[0].corps.membres).toHaveLength(1);
	await expect(conseil.locator('.header-summary')).toContainText('AG 2026');
});

/*  🔴 #1680 — `charger()` recopiait chaque membre champ par champ, SANS son
    identifiant : le PUT recevait des membres inconnus, et le serveur
    supprimait puis recréait tout le conseil à chaque enregistrement — `cree_le`
    remis à l'instant, et autant de « nouveau membre » au fil d'actualité.
    La réconciliation côté serveur (`test_annuaire_cs_reconciliation.py`) ne
    sert que si l'écran rend ce qu'il a lu. */
test('enregistrer sans rien changer renvoie chaque membre avec son identifiant', async ({
	page,
}) => {
	const envois = await ouvrir(page);
	const conseil = section(page, 'Conseil Syndical');
	await conseil.locator('.header-summary').getByRole('button', { name: 'Modifier' }).click();
	await conseil.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0].corps.membres).toHaveLength(1);
	expect(envois[0].corps.membres[0]).toMatchObject({ id: 31, nom: 'Durand' });
});
