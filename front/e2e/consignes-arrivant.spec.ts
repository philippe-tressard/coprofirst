/*
 *  **Les consignes de la fiche arrivant, éditables par le conseil** (#1727).
 *
 *  Espace CS › Annuaire, API simulée. Ce que ce test tient, et qu'aucun
 *  contrôle de source ne verrait :
 *
 *  1. la lecture dit quand ce sont celles du MODÈLE, et non de la résidence ;
 *  2. le crayon ouvre la saisie EN PLACE ; on ajoute et on retire une rubrique ;
 *  3. ce qui PART au serveur est le texte saisi, tel quel (le serveur l'échappe) ;
 *  4. une rubrique vide empêche d'enregistrer, sans rien envoyer ;
 *  5. au bureau comme au téléphone, la page ne défile pas en largeur.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal } from './defilement';

const GABARIT = {
	personnalisees: false,
	consignes: [
		{ titre: '📦 1. Emménagement', contenu: 'Prévenez le conseil **1 semaine** avant.' },
		{ titre: '🗑 2. Encombrants', contenu: 'Aux jours fixés par la commune.' },
	],
};

type Envoi = { consignes: { titre: string; contenu: string }[] };

async function ouvrir(page: Page): Promise<Envoi[]> {
	const envois: Envoi[] = [];
	page.on('request', (r) => {
		if (r.method() === 'PUT' && r.url().includes('/api/admin/consignes-arrivant'))
			envois.push(r.postDataJSON());
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/admin/consignes-arrivant') return GABARIT;
	});
	await page.goto('/espace-cs/annuaire');
	await attendreHydratation(page);
	return envois;
}

const section = (page: Page) =>
	page.locator('section.annuaire-section', {
		has: page.getByRole('heading', { name: 'Consignes de la fiche arrivant', exact: true }),
	});

test.beforeEach(async ({ page }, info) => {
	//  Le téléphone le plus étroit que le site s'engage à tenir.
	if (info.project.name === 'mobile') await page.setViewportSize({ width: 375, height: 812 });
});

test('la lecture dit que ce sont celles du modèle', async ({ page }) => {
	await ouvrir(page);
	const bloc = section(page);
	await expect(bloc).toContainText('Modèle générique');
	await expect(bloc).toContainText('📦 1. Emménagement');
	await expect(bloc).toContainText('Aux jours fixés par la commune.');
	await attendreSansDefilementHorizontal(page);
});

test('le crayon ouvre la saisie en place, et le texte part tel quel', async ({ page }) => {
	const envois = await ouvrir(page);
	const bloc = section(page);
	await bloc.getByRole('button', { name: 'Modifier les consignes' }).click();

	const titres = bloc.getByRole('textbox', { name: /Titre/ });
	await expect(titres).toHaveCount(2);
	//  Retirer la seconde, en ajouter une neuve.
	await bloc.getByRole('button', { name: 'Retirer cette rubrique' }).nth(1).click();
	await bloc.getByRole('button', { name: '+ Nouvelle rubrique' }).click();
	await titres.nth(1).fill('🚲 Vélos');
	await bloc
		.getByRole('textbox', { name: /Texte/ })
		.nth(1)
		.fill('Au **sous-sol**, syndic {syndic}.');

	await bloc.getByRole('button', { name: 'Enregistrer' }).click();
	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0].consignes).toEqual([
		GABARIT.consignes[0],
		{ titre: '🚲 Vélos', contenu: 'Au **sous-sol**, syndic {syndic}.' },
	]);
	//  La saisie se referme sur la lecture.
	await expect(titres).toHaveCount(0);
});

test('une rubrique vide empêche d’enregistrer, sans rien envoyer', async ({ page }) => {
	const envois = await ouvrir(page);
	const bloc = section(page);
	await bloc.getByRole('button', { name: 'Modifier les consignes' }).click();
	await bloc.getByRole('textbox', { name: /Titre/ }).first().fill('');
	await expect(bloc.getByRole('button', { name: 'Enregistrer' })).toBeDisabled();
	expect(envois).toEqual([]);
});
