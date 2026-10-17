/*
 *  **Admin › Pages légales : le constat « à relire » se voit, et se lève** (#2065).
 *
 *  Une copropriété neuve reçoit le gabarit du produit, dont les champs nomment
 *  SON syndicat et SON syndic. Tant que les textes ne sont pas relus — ou disent
 *  encore « À RENSEIGNER » —, l'onglet le dit, texte par texte, avec ce qui manque
 *  et où le renseigner. Le geste « J'ai relu ces textes » part au serveur, qui
 *  rend le nouveau constat ; l'onglet ne le recalcule pas.
 *
 *  Et la source n'est pas le rendu : l'éditeur reçoit les champs `[[…]]`.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const A_RELIRE = {
	a_relire: true,
	textes: [
		{
			cle: 'mentions_legales',
			titre: 'Mentions légales',
			relu: false,
			relu_le: null,
			complet: false,
			manques: ['le nom du syndic — Annuaire › Syndic'],
			a_relire: true,
		},
		{
			cle: 'politique_confidentialite',
			titre: 'Politique de confidentialité',
			relu: false,
			relu_le: null,
			complet: true,
			manques: [],
			a_relire: true,
		},
	],
};
const RELUS = {
	a_relire: false,
	textes: A_RELIRE.textes.map((t) => ({
		...t,
		relu: true,
		relu_le: '2026-10-17T10:00:00',
		complet: true,
		manques: [],
		a_relire: false,
	})),
};

async function ouvrir(page: Page): Promise<string[]> {
	const envois: string[] = [];
	page.on('request', (r) => {
		const url = new URL(r.url());
		if (url.pathname.startsWith('/api/') && r.method() !== 'GET')
			envois.push(`${r.method()} ${url.pathname}`);
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/textes-legaux')
			return {
				textes: {
					mentions_legales: '<h2>Éditeur du service</h2><p>Le syndic, [[syndic]].</p>',
					politique_confidentialite: '<p>Responsable : [[copropriete]].</p>',
				},
				champs: [
					{
						nom: 'copropriete',
						libelle: 'le nom',
						ou: 'Fiche copropriété',
						valeur: 'Les Tilleuls',
					},
					{ nom: 'syndic', libelle: 'le nom du syndic', ou: 'Annuaire › Syndic', valeur: null },
				],
				contact: '',
				etat: A_RELIRE,
			};
		if (chemin === '/api/config/textes-legaux/relecture') return RELUS;
	});
	await page.goto('/admin?onglet=legal');
	await attendreHydratation(page);
	return envois;
}

test('les textes à relire le disent, avec ce qui manque et où le renseigner', async ({ page }) => {
	await ouvrir(page);
	await expect(page.getByText(/Ces textes engagent le syndicat/)).toBeVisible();
	await expect(page.getByText('Mentions légales à relire')).toBeVisible();
	await expect(
		page.getByText('le nom du syndic — Annuaire › Syndic', { exact: true }),
	).toBeVisible();
	//  La valeur d'un champ, et l'absence d'une autre, dite avec sa place.
	await expect(page.getByText('Les Tilleuls')).toBeVisible();
	await expect(page.getByText('À renseigner', { exact: true })).toBeVisible();
	//  L'éditeur reçoit la SOURCE : le champ, pas un nom.
	await expect(page.locator('.tiptap').first()).toContainText('[[syndic]]');
});

test('« J’ai relu ces textes » part au serveur, et l’onglet suit son constat', async ({ page }) => {
	const envois = await ouvrir(page);
	await page.getByRole('button', { name: 'J’ai relu ces textes' }).click();
	await expect.poll(() => envois).toContain('POST /api/config/textes-legaux/relecture');
	await expect(page.getByText('Mentions légales relue')).toBeVisible();
	await expect(page.getByRole('button', { name: 'J’ai relu ces textes' })).toHaveCount(0);
});
