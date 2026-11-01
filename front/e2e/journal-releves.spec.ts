/*
 *  **Le journal des messages relevés se lit dans Espace CS › Courriels (#1447).**
 *
 *  Le 28/09/2026, un message a été ignoré sans qu'on puisse dire pourquoi ; le
 *  05/10/2026, un transfert refusé (numéro d'affaire mal tapé) n'était lisible que
 *  de l'administrateur. Ce test rend le VRAI onglet, API simulée, et lit ce que le
 *  conseil voit : une pliure par message, chaque verdict — ignoré compris — avec
 *  son motif, le lien vers l'affaire, et aucune adresse trop longue qui
 *  élargirait la page au téléphone.
 *
 *  Le même rendu sert l'historique WhatsApp (`JournalVerdicts`) : le second
 *  test vérifie qu'il n'a rien perdu en changeant de composant.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal } from './defilement';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const ligne = (id: number, decision: string, motif: string, extra = {}) => ({
	id,
	releve_le: `2026-09-28T1${id}:00:00`,
	envoye_le: null,
	//  Le conseil ne reçoit que le NOM : le serveur ne lui envoie pas l'adresse.
	expediteur: 'Gestionnaire',
	objet: 'Re: Affaire #TK-121048 - Porte du hall',
	decision,
	motif,
	ticket_id: null,
	affaire: null,
	...extra,
});

const RELEVES = [
	ligne(4, 'ignore', 'ne répond à aucun ticket', {
		//  Sans espace : c'est elle qui élargirait la page si rien ne la coupait.
		expediteur:
			'Un.nom.particulierement.long.sans.aucune.espace.ni.le.moindre.tiret.pour.le.couper.exemple',
		objet: 'absente cette semaine',
	}),
	ligne(3, 'refuse', 'la signature ne couvre qu’une partie du message', {
		ticket_id: 7,
		affaire: 'TK-121048',
	}),
	ligne(2, 'relance', 'réponse à une relance groupée, transmise au conseil syndical'),
	ligne(1, 'accepte', 'ajouté au fil de l’affaire — signé par syndic.fr', {
		ticket_id: 7,
		affaire: 'TK-121048',
	}),
];

test('Espace CS › Courriels : une pliure par message, verdict et motif dessous', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return MEMBRE_CS;
		if (chemin === '/api/courriels-affaires') return { limite: 20, messages: RELEVES };
		return undefined;
	});
	await page.goto('/espace-cs/courriels');

	const bloc = page.locator('.jv-liste');
	await expect(bloc).toBeVisible();
	const lignes = bloc.locator('.jv-ligne');
	await expect(lignes).toHaveCount(4);
	await expect(page.getByText('Les 20 derniers messages')).toBeVisible();

	//  Le plus récent d'abord, tel que le serveur l'a rendu ; chaque verdict se lit
	//  sur la pliure FERMÉE, le motif ne vient qu'à l'ouverture.
	await expect(lignes.nth(0).locator('summary .badge')).toHaveText('Ignoré');
	await expect(lignes.nth(1).locator('summary .badge')).toHaveText('Refusé');
	await expect(lignes.nth(1).locator('summary .badge')).toHaveClass(/badge-orange/);
	await expect(lignes.nth(2).locator('summary .badge')).toHaveText('Transmis au conseil');
	await expect(lignes.nth(3).locator('summary .badge')).toHaveClass(/badge-green/);
	await expect(lignes.nth(0).locator('.jv-texte')).toBeHidden();

	//  Une pliure s'ouvre : l'IGNORÉ dit pourquoi, l'affaire se rouvre d'un clic.
	await lignes.nth(0).locator('summary').click();
	await expect(lignes.nth(0).locator('.jv-texte')).toHaveText('ne répond à aucun ticket');
	await expect(lignes.nth(0).getByRole('link')).toHaveCount(0);

	//  Un seul bloc ouvert à la fois (règle 17) : ouvrir la suivante referme la première.
	await lignes.nth(3).locator('summary').click();
	await expect(lignes.nth(3).getByRole('link', { name: 'Affaire #TK-121048' })).toHaveAttribute(
		'href',
		'/tickets/7',
	);
	await expect(lignes.nth(0).locator('.jv-texte')).toBeHidden();

	//  Le conseil lit le nom, jamais l'adresse : le serveur ne l'envoie pas.
	await expect(page.getByText('@')).toHaveCount(0);

	await attendreSansDefilementHorizontal(page, 'dans l’onglet Courriels');
	//  La page peut ne pas déborder alors qu'une ligne sort de son cadre (le
	//  conteneur coupe) : c'est la LIGNE qu'on mesure — ce contrôle a été vu
	//  passer au vert sans `overflow-wrap` tant qu'il ne regardait que la page.
	await lignes.nth(0).locator('summary').click();
	const lignesDebordent = await lignes.evaluateAll((els) =>
		els.some((el) => el.scrollWidth > el.clientWidth + 1),
	);
	expect(lignesDebordent, 'une ligne du journal déborde de son cadre').toBe(false);

	await bloc.screenshot({
		path: `test-results/journal-releves-${test.info().project.name}.png`,
	});
});

test('Paramétrage › SMTP : le journal renvoie vers Espace CS, le nombre affiché se règle', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		return undefined;
	});
	await page.goto('/admin?onglet=smtp');
	await expect(page.getByRole('link', { name: 'Espace CS › Courriels' })).toHaveAttribute(
		'href',
		'/espace-cs/courriels',
	);
	await expect(page.getByLabel('Messages affichés dans Espace CS › Courriels')).toBeVisible();
	await expect(page.locator('.jv-liste')).toHaveCount(0);
});

test('WhatsApp : l’historique des envois garde ses trois issues', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/whatsapp-logs')
			return [
				{
					id: 2,
					label: 'Encombrants',
					message: 'Demain.',
					statut: 'incertain',
					erreur: null,
					envoye_le: '2026-09-28T10:00:00',
				},
				{
					id: 1,
					label: 'Ascenseur',
					message: 'Réparé.',
					statut: 'échec',
					erreur: 'bridge absent',
					envoye_le: '2026-09-27T10:00:00',
				},
			];
		return undefined;
	});
	await page.goto('/admin?onglet=whatsapp');

	const lignes = page.locator('.jv-ligne');
	await expect(lignes).toHaveCount(2);
	await expect(lignes.nth(0).locator('.badge')).toHaveText('⚠️ incertain');
	await expect(lignes.nth(0).locator('.badge')).toHaveClass(/badge-orange/);
	await expect(lignes.nth(1).locator('.badge')).toHaveClass(/badge-red/);
	await expect(lignes.nth(1)).toContainText('bridge absent');
});
