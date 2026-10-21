/*
 *  **La carte d'une affaire close, dépliée — maquette G** (arbitrée le 16/10/2026).
 *
 *  Repliée, la carte dit qu'une synthèse validée l'accompagne (🧾 Synthèse).
 *  Dépliée, elle se lit en trois ÉTAPES, dans cet ordre : la DEMANDE, la SUITE,
 *  la SYNTHÈSE. Une seule s'ouvre à la fois, la demande d'abord ; pliée, chacune
 *  dit l'essentiel sur une ligne. La synthèse : texte d'abord, puis les chiffres,
 *  la chronologie pliée. La suite : trois entrées, les plus anciennes repliées,
 *  sans la Suite de synthèse ; chaque entrée porte crayon et corbeille au trait,
 *  et la corbeille demande confirmation avant d'effacer.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';
import { AFFAIRE, ETAT_SYNTHESE, FIL } from './affaire-close-donnees';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

async function ouvrir(page: Page, moi = MEMBRE_CS) {
	const effacees: string[] = [];
	page.on('request', (r) => {
		if (r.method() === 'DELETE') effacees.push(new URL(r.url()).pathname);
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return moi;
		if (chemin === '/api/tickets') return [AFFAIRE];
		if (chemin === '/api/tickets/42') return AFFAIRE;
		if (chemin === '/api/tickets/42/evolutions') return FIL;
		if (chemin === '/api/tickets/42/synthese') return ETAT_SYNTHESE;
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	return effacees;
}

/**  L'en-tête d'une étape — le bouton qui la plie et la déplie. */
const etape = (page: Page, titre: string) =>
	page.locator('.carte-liste').first().locator('.encart-tete', { hasText: titre });

test('dépliée, trois étapes dans l’ordre, une seule ouverte à la fois', async ({ page }) => {
	await ouvrir(page);
	const carte = page.locator('.carte-liste').first();
	await expect(carte).toContainText('🧾 Synthèse');

	await carte.getByText(AFFAIRE.titre).click();
	const corps = carte.locator('.carte-corps');
	await expect(corps.locator('.encart-titre')).toHaveText([
		/^La demande$/,
		/^La suite\s*5 entrées$/,
		/^La synthèse$/,
	]);
	//  La demande d'abord ; les autres pliées, et leur ligne dit l'essentiel.
	await expect(etape(page, 'La demande')).toHaveAttribute('aria-expanded', 'true');
	await expect(etape(page, 'La suite')).toHaveAttribute('aria-expanded', 'false');
	await expect(etape(page, 'La suite')).toContainText('Résolu le 21 oct. 2026');
	await expect(etape(page, 'La synthèse')).toContainText(
		'Validée le 22 oct. 2026 · affaire close en 8 j',
	);
	await expect(corps.getByText('Raccord de la colonne remplacé')).toBeHidden();

	//  Ouvrir la synthèse replie la demande.
	await etape(page, 'La synthèse').click();
	await expect(etape(page, 'La synthèse')).toHaveAttribute('aria-expanded', 'true');
	await expect(etape(page, 'La demande')).toHaveAttribute('aria-expanded', 'false');
	await expect(corps.getByText('Une tache s’étend au plafond du hall.')).toBeHidden();
	//  Le texte de la synthèse se lit AVANT ses chiffres.
	await expect
		.poll(async () => {
			const texte = await corps.innerText();
			return texte.indexOf('Raccord de la colonne remplacé') < texte.indexOf('Les chiffres');
		})
		.toBe(true);
	//  La chronologie est pliée.
	await expect(corps.locator('details.plies')).not.toHaveAttribute('open', '');

	//  La suite : trois entrées, puis les plus anciennes — sans la Suite de synthèse.
	await etape(page, 'La suite').click();
	await expect(etape(page, 'La synthèse')).toHaveAttribute('aria-expanded', 'false');
	await expect(corps.locator('.evol-item')).toHaveCount(3);
	await expect(
		corps.getByRole('button', { name: /Voir les 2 entrées plus anciennes/ }),
	).toBeVisible();
	await expect(corps.locator('.evol-item').first()).toContainText('Résolu');
});

test('la corbeille d’une entrée demande confirmation avant d’effacer', async ({ page }) => {
	const effacees = await ouvrir(page, ADMIN);
	const carte = page.locator('.carte-liste').first();
	await carte.getByText(AFFAIRE.titre).click();
	await etape(page, 'La suite').click();

	const premiere = carte.locator('.evol-item').first();
	await expect(premiere.getByRole('button', { name: 'Modifier cette entrée' })).toBeVisible();
	await premiere.getByRole('button', { name: 'Supprimer cette entrée' }).click();

	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('L’état de l’affaire ne change pas');
	await boite.getByRole('button', { name: 'Annuler' }).click();
	expect(effacees, 'Annuler n’efface rien').toHaveLength(0);

	await premiere.getByRole('button', { name: 'Supprimer cette entrée' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Supprimer' }).click();
	await expect.poll(() => effacees).toEqual(['/api/tickets/42/evolutions/5']);
});
