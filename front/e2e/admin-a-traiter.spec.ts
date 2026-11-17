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
import { attendreSansDefilementHorizontal } from './defilement';

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

/**
 *  Les lectures de l'onglet Modèles e-mail ne partent que 500 ms après son
 *  montage (#2807) : la fenêtre que le CI n'ouvrait qu'au hasard, ouverte à
 *  chaque passage. Chacune, en partant, le dit au test (`lectureTardivePartie`,
 *  liaison exposée : une requête que WebKit bloque n'émet aucun `request`). Le
 *  reste du site appelle `fetch` tel quel.
 */
function LECTURES_TARDIVES() {
	const envoyer = window.fetch;
	const partie = () =>
		(window as unknown as { lectureTardivePartie?: () => void }).lectureTardivePartie?.();
	window.fetch = (entree, options) =>
		/\/api\/admin\/(modeles-email|emails\/historique)$/.test(String(entree))
			? new Promise((fin) => setTimeout(fin, 500)).then(() => {
					const reponse = envoyer(entree, options);
					partie();
					return reponse;
				})
			: envoyer(entree, options);
}

test('Admin › À traiter : trois sections en accordéon, Télémétrie en gestion @mise-en-page', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/comptes-en-attente/enrichis') return [];
		if (chemin === '/api/admin/commandes-acces') return COMMANDES;
		if (chemin === '/api/admin/demandes-profil') return DEMANDES;
		return undefined;
	});
	let parties = 0;
	let toutesParties!: () => void;
	const lecturesParties = new Promise<void>((fin) => (toutesParties = fin));
	await page.exposeFunction('lectureTardivePartie', () => {
		if (++parties === 2) toutesParties();
	});
	await page.addInitScript(LECTURES_TARDIVES);
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
	//
	//  🔴 #2807 (16/11/2026). L'onglet arrive au geste (`ChargementDiffere`) et ne
	//  lance ses deux lectures qu'une fois monté. Le `page.goto` qui suit partait
	//  sans l'attendre : quand le module arrivait tard, les lectures partaient
	//  PENDANT la navigation, et WebKit le dit en console — `Fetch API cannot
	//  load … due to access control checks.`, même rejet rattrapé —, ce que
	//  Playwright WebKit compte comme une exception de la page. Le test attend
	//  donc l'état final de l'onglet avant de le quitter.
	//
	//  Ce chemin lent n'était joué qu'au hasard : il l'est à chaque fois. Les deux
	//  lectures de l'onglet partent tard (`LECTURES_TARDIVES`), et la page suivante
	//  est retenue tant qu'elles ne sont pas parties : sans l'attente de l'état
	//  final, elles partent pendant la navigation, et le test échoue à coup sûr.
	await page.locator('.groupe', { hasText: 'Présentation' }).click();
	await page.locator('.tab-btn', { hasText: 'Modèles e-mail' }).click();
	await expect(page).toHaveURL(/\/admin\?onglet=emails$/);
	await expect(page.locator('.tab-descriptif')).toContainText('chaque courriel envoyé par le site');
	await expect(page.locator('.intro-modeles')).toBeVisible();
	//  L'état final : les deux lectures sont faites, l'API simulée rend une liste vide.
	await expect(page.getByText('Aucun modèle trouvé')).toBeVisible();

	//  … et « Descriptif pages » les propose à la modification, comme ailleurs.
	await page.route(
		(u) => u.pathname === '/admin' && u.searchParams.get('onglet') === 'pages',
		async (route) => {
			await lecturesParties;
			await route.continue();
		},
		{ times: 1 },
	);
	await page.goto('/admin?onglet=pages');
	await page.locator('.page-row-btn', { hasText: 'Paramétrage' }).click();
	const cartes = page.locator('.onglet-card');
	//  19 depuis l'onglet « Installations » du registre (#1880) — et toujours 19
	//  après le rangement par niveau (#2062) : quatre partis, quatre venus. 20 depuis
	//  l'onglet « Lots » de Copropriété (#2216), 21 depuis « Équipements » (#2442).
	await expect(cartes).toHaveCount(21);
	await expect(cartes.first().locator('input').first()).toHaveValue('À traiter');

	await attendreSansDefilementHorizontal(page);
});

/*
 *  L'autre sens de #2807 : la console de WebKit ne se tait pas en rattrapant les
 *  erreurs réseau. Une vraie panne — le serveur injoignable — se dit à l'écran,
 *  sous Chromium comme sous WebKit, et sans exception de la page.
 */
test('Admin › Modèles e-mail : une panne réseau se dit à l’écran, sans exception @moteur', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await page.route(
		(u) => /^\/api\/admin\/(modeles-email|emails\/historique)$/.test(u.pathname),
		(route) => route.abort('failed'),
	);
	await page.goto('/admin?onglet=emails');
	await expect(page.getByText('Impossible d’afficher les modèles d’e-mail')).toBeVisible();
	await expect(page.getByText('Chargement impossible')).toHaveCount(2);
});
