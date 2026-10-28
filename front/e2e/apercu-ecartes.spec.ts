/*
 *  **L'aperçu nomme qui ne recevra rien** (#2006, 15/10/2026).
 *
 *  Un commentaire adressé au conseil n'a pas atteint deux de ses membres, que
 *  l'aperçu annonçait pourtant : l'envoi les écartait ensuite, sans un mot. Le
 *  serveur rend désormais `ecartes` — tri par la fonction même de l'envoi — et
 *  l'écran les montre sous « Ne recevront rien », avec le motif.
 */
import type { ApercuDiffusion } from '#lib/api/index.ts';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const APERCU: ApercuDiffusion = {
	canaux: [
		{
			canal: 'email',
			actif: true,
			destinataires: ['durand@exemple.test'],
			ecartes: [{ qui: 'Paul MARTIN', motif: 'pas d’adresse renseignée' }],
			sujet: 'Affaire — Fuite',
			corps_html: '<p>Fuite</p>',
			ampute: false,
			avec_photo: false,
		},
	],
	attribues_a_la_creation: [],
};

test('L’aperçu de la Diffusion nomme le membre écarté et son motif', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets/apercu-diffusion') return APERCU;
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();
	await page
		.getByText(/Ascenseur, chauffage, éclairage/)
		.first()
		.click();
	await page.getByLabel(/Titre/).first().fill('Fuite au sous-sol');
	await page
		.getByLabel(/Description/)
		.first()
		.fill('Une fuite sous la colonne.');
	await page
		.getByRole('button', { name: /^Créer|^Enregistrer|^Signaler/ })
		.first()
		.click();

	const ecartes = page.locator('.apercu-ecartes');
	await expect(ecartes).toContainText('Ne recevront rien');
	await expect(ecartes).toContainText('Paul MARTIN — pas d’adresse renseignée');
	await expect(page.getByText('durand@exemple.test')).toBeVisible();
});
