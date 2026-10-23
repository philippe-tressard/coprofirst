/*
 *  **Un transfert de courriel versé par erreur se défait depuis l'affaire** (#1482).
 *
 *  Demandé le 30/09/2026 : annuler en une fois, réaffecter à une autre affaire,
 *  ou en faire une nouvelle. La règle est au serveur
 *  (`api/tests/test_versement_transfert.py`) ; ce test-ci vérifie ce que l'écran
 *  en MONTRE — API simulée, compte CS :
 *
 *  - aucun bloc quand il n'y a rien à défaire ;
 *  - un transfert retenu par un suivant dit pourquoi, et ne propose que
 *    « Valider » — celui que plus rien ne rouvrira n'est pas servi (14/10/2026) ;
 *  - « Valider le transfert » (13/10/2026) demande confirmation, puis appelle
 *	sa route — sur un transfert défaisable comme sur un bloqué ;
 *  - « Annuler » demande confirmation, puis appelle la bonne route ;
 *  - « Déplacer » ne propose ni l'affaire ouverte, ni une affaire close ;
 *  - le bloc est AUSSI dans la carte dépliée de la liste, et un geste y relit
 *    l'affaire (01/10/2026 : il n'était que sur la fiche, que la carte n'ouvre
 *    pas — TK-109008 ne se défaisait qu'en retrouvant la notification) ;
 *  - le lien direct n'a qu'un bord droit : la barre « Répondre » s'étalait
 *    jusqu'au bord de l'écran, sa largeur posée par la page sur une classe que
 *    l'extraction du fil avait emportée. Depuis le 15/10/2026 le lien rend la
 *    CARTE dépliée — transferts et fil compris — et le fil des messages dessous.
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';

const AFFAIRE = {
	id: 7,
	numero: 'TK-109008',
	titre: 'Portillon bloqué',
	description: 'Mail reçu de Jean Dupont…',
	categorie: 'etude_travaux',
	statut: 'en_cours',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	cree_le: '2026-09-29T10:00:00',
	mis_a_jour_le: '2026-09-29T10:00:00',
	perimetre_cible: [],
	photos_urls: [],
	fichiers_urls: [],
};
const DEFAISABLE = {
	id: 11,
	cree_le: '2026-09-30T12:05:00',
	transfere_par_nom: 'CS Témoin',
	suites: 3,
	affaire_creee: false,
	bloque: null,
	peut_deplacer: true,
};
const BLOQUE = {
	...DEFAISABLE,
	id: 10,
	suites: 1,
	bloque: "un transfert suivant a été versé dans cette affaire : annulez-le d'abord",
};
const CHOIX = [
	{ id: 7, numero: 'TK-109008', titre: 'Portillon bloqué', statut: 'en_cours' },
	{ id: 8, numero: 'TK-200001', titre: 'Portail du parking', statut: 'ouvert' },
	{ id: 9, numero: 'TK-200002', titre: 'Portillon ancien', statut: 'résolu' },
];

/** Les gestes du bloc, interceptés : ce qu'ils appellent, et rien d'autre. */
async function intercepterGestes(page: Page): Promise<string[]> {
	const appels: string[] = [];
	//  Déclarée APRÈS `simulerApi` : Playwright essaie d'abord la dernière route.
	await page.route(
		(url) => url.pathname.startsWith('/api/tickets/7/transferts/'),
		(route) => {
			appels.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({ ticket_id: 7, numero: 'TK-109008' }),
			});
		},
	);
	return appels;
}

async function simuler(page: Page, transferts: unknown[]) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [AFFAIRE];
		if (chemin === '/api/tickets/7') return AFFAIRE;
		if (chemin === '/api/tickets/7/transferts') return transferts;
		if (chemin === '/api/tickets/choix') return CHOIX;
	});
}

test('rien à défaire : aucun bloc', async ({ page }) => {
	await simuler(page, []);
	await page.goto('/tickets/7');
	await expect(page.locator('.carte-liste', { hasText: 'Portillon bloqué' })).toBeVisible();
	await expect(page.getByText('Transferts de courriel')).toHaveCount(0);
});

test('un transfert se défait d’un geste, un transfert bloqué dit pourquoi', async ({ page }) => {
	await simuler(page, [DEFAISABLE, BLOQUE]);
	const appels = await intercepterGestes(page);

	await page.goto('/tickets/7');
	const bloc = page.locator('section.transferts');
	await expect(bloc.getByText('Transferts de courriel')).toBeVisible();
	const [premier, second] = [bloc.locator('.transfert').nth(0), bloc.locator('.transfert').nth(1)];
	await expect(premier).toContainText('3 suites');
	await expect(second).toContainText('Ne se défait pas encore');
	await expect(second.getByRole('button')).toHaveCount(1);
	await expect(second.getByRole('button', { name: 'Valider le transfert' })).toBeVisible();

	await bloc.screenshot({
		path: `test-results/transferts-verses-${test.info().project.name}.png`,
	});

	//  Déplacer : ni l'affaire ouverte, ni une affaire close.
	await premier.getByRole('button', { name: /Déplacer vers une autre affaire/ }).click();
	await premier.getByLabel('Vers l’affaire').focus();
	const propositions = premier.locator('.proposition');
	await expect(propositions).toHaveCount(1);
	await expect(propositions).toContainText('TK-200001');
	await bloc.screenshot({
		path: `test-results/transferts-deplacer-${test.info().project.name}.png`,
	});

	//  Annuler : une confirmation, puis la route du geste.
	await premier.getByRole('button', { name: 'Annuler le transfert' }).click();
	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('quitteront cette affaire');
	await boite.getByRole('button', { name: 'Annuler le transfert' }).click();
	await expect.poll(() => appels).toEqual(['POST /api/tickets/7/transferts/11/annuler']);
});

test('valider un transfert, défaisable ou bloqué, appelle sa route', async ({ page }) => {
	await simuler(page, [DEFAISABLE, BLOQUE]);
	const appels = await intercepterGestes(page);

	await page.goto('/tickets/7');
	const bloc = page.locator('section.transferts');
	const [premier, second] = [bloc.locator('.transfert').nth(0), bloc.locator('.transfert').nth(1)];
	await expect(premier.getByRole('button')).toHaveCount(4);

	await premier.getByRole('button', { name: 'Valider le transfert' }).click();
	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('ne pourra plus être annulé ni déplacé');
	await boite.getByRole('button', { name: 'Valider', exact: true }).click();
	await expect.poll(() => appels).toEqual(['POST /api/tickets/7/transferts/11/valider']);

	await second.getByRole('button', { name: 'Valider le transfert' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Valider', exact: true }).click();
	await expect
		.poll(() => appels)
		.toEqual([
			'POST /api/tickets/7/transferts/11/valider',
			'POST /api/tickets/7/transferts/10/valider',
		]);
});

test('la carte dépliée de la liste offre le même geste, et relit l’affaire', async ({ page }) => {
	await simuler(page, [DEFAISABLE]);
	const appels = await intercepterGestes(page);
	const relectures: string[] = [];
	page.on('request', (r) => {
		const chemin = new URL(r.url()).pathname;
		if (chemin === '/api/tickets/7' || chemin === '/api/tickets/7/evolutions')
			relectures.push(chemin);
	});

	await page.goto('/tickets');
	const carte = page.locator('.carte-liste', { hasText: 'Portillon bloqué' });
	//  Par le titre : au téléphone, le centre de la carte peut tomber sur la
	//  rangée d'icônes, passée sous un titre qui ne tient pas à côté (23/10/2026).
	await carte.getByRole('button', { name: /Portillon bloqué/ }).click();
	const bloc = carte.locator('section.transferts');
	await expect(bloc.getByText('Transferts de courriel')).toBeVisible();
	//  Pas de carte dans la carte (#425) : le bloc n'y porte pas `.card`.
	await expect(bloc).not.toHaveClass(/(^|\s)card(\s|$)/);
	await carte.screenshot({ path: `test-results/transferts-carte-${test.info().project.name}.png` });

	relectures.length = 0;
	await bloc.getByRole('button', { name: 'Annuler le transfert' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Annuler le transfert' }).click();
	await expect.poll(() => appels).toEqual(['POST /api/tickets/7/transferts/11/annuler']);
	//  Le geste a pu changer le statut, retirer des Suites, archiver : la liste relit les deux.
	await expect
		.poll(() => [...new Set(relectures)].sort())
		.toEqual(['/api/tickets/7', '/api/tickets/7/evolutions']);
});

test('le lien direct n’a qu’un bord droit — la barre « Répondre » comprise', async ({ page }) => {
	await simuler(page, [DEFAISABLE]);
	await page.goto('/tickets/7');
	const blocs = {
		carte: page.locator('.affaire-seule .carte-liste'),
		Répondre: page.locator('.carte-repondre'),
	};
	const bords: Record<string, number> = {};
	for (const [nom, bloc] of Object.entries(blocs)) {
		//  Cas zéro : un bloc absent ne prouverait rien sur sa largeur.
		await expect(bloc, `le bloc « ${nom} » n’est pas rendu`).toBeVisible();
		const boite = await bloc.boundingBox();
		bords[nom] = Math.round((boite?.x ?? 0) + (boite?.width ?? 0));
	}
	const reference = bords.carte;
	for (const [nom, bord] of Object.entries(bords)) {
		expect(bord, `le bloc « ${nom} » ne s’arrête pas au bord de la carte`).toBe(reference);
	}
});
