/*
 *  **Une intervention dit si elle est sous contrat (#1445).**
 *
 *  Une affaire désignait un prestataire, jamais le contrat : il était DEVINÉ
 *  (libellé dans le titre), et un dépannage hors contrat avançait la visite
 *  d'entretien. La section Intervenant offre désormais le cadre — sous contrat
 *  (lequel) ou hors contrat — quand le prestataire a des contrats en cours ; et
 *  sous contrat, la fréquence se LIT sur le contrat.
 *
 *  Le test rend le vrai formulaire, API simulée : c'est l'écran qui décide
 *  d'offrir le choix, et de taire la fréquence — aucun test unitaire ne le voit.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const OTIS = { id: 1, nom: 'Otis', specialite: 'ascenseur', actif: true };
const MARTIN = { id: 2, nom: 'Plomberie Martin', specialite: 'plomberie', actif: true };
const CONTRAT = {
	id: 10,
	prestataire_id: 1,
	libelle: 'Maintenance ascenseur',
	type_equipement: 'ascenseur',
	frequence_type: 'mois',
	frequence_valeur: 1,
	actif: true,
};

const section = (page: Page, titre: string) =>
	page.locator('section.section-formulaire', {
		has: page.locator('.section-titre-texte', { hasText: titre }),
	});

async function nouvelEntretien(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/prestataires') return [OTIS, MARTIN];
		if (chemin === '/api/prestataires/contrats') return [CONTRAT];
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();
	await page
		.getByText(/Visite ou maintenance d’un prestataire/)
		.first()
		.click();
	const intervenant = section(page, 'Intervenant');
	//  Pliée quand elle est vide : on l'ouvre comme on le ferait. La section
	//  rendue d'abord — sinon `isVisible` jugerait l'instant (#1830).
	await expect(intervenant).toBeVisible();
	if (!(await intervenant.locator('select').first().isVisible()))
		await intervenant.locator('.section-titre-texte').click();
	return intervenant;
}

test('un prestataire sous contrat offre le cadre, et la fréquence devient celle du contrat', async ({
	page,
}) => {
	const intervenant = await nouvelEntretien(page);
	const cadre = intervenant.getByLabel(/Cadre de l.intervention/);
	await expect(cadre, 'aucun intervenant : pas de cadre à choisir').toHaveCount(0);

	await intervenant.locator('select').first().selectOption('1');
	await expect(cadre).toBeVisible();
	await expect(cadre).toHaveValue('');
	await cadre.selectOption('10');

	//  VISIBLE, sans ouvrir « Quand » : le rythme du contrat est une valeur, et une
	//  valeur rouvre sa section pliée (`ux-patterns` §0) — elle restait pliée.
	await expect(page.getByText(/Fréquence : ↺ Mensuel —\u00a0celle du contrat/)).toBeVisible();
	await expect(page.getByRole('group', { name: 'Fréquence' })).toHaveCount(0);
});

test('un prestataire sans contrat ne propose pas « hors contrat »', async ({ page }) => {
	const intervenant = await nouvelEntretien(page);
	await intervenant.locator('select').first().selectOption('2');
	await expect(intervenant.getByLabel(/Cadre de l.intervention/)).toHaveCount(0);
});
