/*
 *  **Supprimer les lues, en une requête (#2535).**
 *
 *  La page Notifications n'offrait qu'une corbeille par ligne : vider les lues d'un
 *  compte de 146 alertes coûtait autant de gestes. Ce que le test tient : le bouton
 *  n'apparaît que s'il y a des lues, il demande confirmation (suppression
 *  définitive), envoie UNE requête `POST /notifications/supprimer-lues`, et la liste
 *  ne garde que les non lues.
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal, elargirLeTexte } from './defilement';

const notif = (id: number, lue: boolean) => ({
	id,
	type: 'system',
	titre: `Avis ${id}`,
	corps: '',
	lien: null,
	lue,
	urgente: false,
	cree_le: '2026-11-01T09:00:00',
});

async function ouvrir(page: Page, liste: ReturnType<typeof notif>[]) {
	await simulerApi(page, (api) => {
		if (api === '/api/notifications') return liste;
		if (api === '/api/notifications/supprimer-lues') return { supprimees: 2 };
	});
	await page.goto('/notifications');
}

test('les lues partent en une requête, les non lues restent @mise-en-page', async ({ page }) => {
	await ouvrir(page, [notif(1, false), notif(2, true), notif(3, true)]);
	await expect(page.getByText('Avis 1')).toBeVisible(); //  cas zéro
	await expect(page.getByText('Avis 2')).toBeVisible();
	//  Trois éléments dans l'en-tête au pouce : compte, « Tout marquer lu », ce geste.
	await elargirLeTexte(page);
	await attendreSansDefilementHorizontal(page, 'en-tête des notifications');

	await page.getByRole('button', { name: 'Supprimer les lues' }).click();
	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('Les 2 notifications lues');
	await expect(boite).toContainText('irréversible');

	const requete = page.waitForRequest(
		(r) => r.method() === 'POST' && r.url().endsWith('/api/notifications/supprimer-lues'),
	);
	await boite.getByRole('button', { name: 'Supprimer' }).click();
	await requete;

	await expect(page.getByText('Avis 2')).toHaveCount(0);
	await expect(page.getByText('Avis 3')).toHaveCount(0);
	await expect(page.getByText('Avis 1')).toBeVisible();
	await expect(page.getByRole('button', { name: 'Supprimer les lues' })).toHaveCount(0);
});

test('sans notification lue, le geste ne s’offre pas', async ({ page }) => {
	await ouvrir(page, [notif(1, false)]);
	await expect(page.getByText('Avis 1')).toBeVisible(); //  cas zéro
	await expect(page.getByRole('button', { name: 'Supprimer les lues' })).toHaveCount(0);
});
