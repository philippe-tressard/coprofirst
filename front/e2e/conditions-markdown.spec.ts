/*
 *  **Les conditions d'inscription se lisent mises en forme** (#1930, 14/10/2026).
 *
 *  Le texte (`api/app/registre/conditions/v*.md`) s'affichait BRUT dans le
 *  formulaire d'inscription : astérisques du gras, liens entre crochets,
 *  chevrons de citation. Il passe désormais par `TexteMarkdown` (`marked`, puis
 *  `safeHtml`). Ce test tient ce que seul un écran montre : la mise en forme, le
 *  lien qui s'ouvre à côté, et un HTML injecté dans le texte qui ne s'exécute pas
 *  — le texte archivé d'une fiche du registre vient d'une AUTRE installation.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

//  La carte d'installation est réservée à l'opérateur de la plateforme (`$isOperateur`).
const OPERATEUR = { ...MEMBRE_CS, role: 'admin', roles: ['admin', 'operateur'] };

const TEXTE = [
	'# Conditions d’inscription',
	'',
	'**Version : 1** — un projet.',
	'',
	'> Ce texte n’est pas un avis juridique.',
	'',
	'Voir la [licence](https://exemple.test/LICENSE).',
	'',
	'<img src="x" onerror="window.__xss = 1"><script>window.__xss = 2</script>',
].join('\n');

test('le formulaire d’inscription montre les conditions mises en forme, sans HTML actif', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return OPERATEUR;
		if (chemin === '/api/admin/installation/inscription')
			return {
				etat: 'limitee',
				raison: 'Non inscrite.',
				identifiant: null,
				canal: null,
				version_cible: null,
				services: null,
				epoque: null,
				echeance: null,
				renouvellement_en_retard: false,
				inscrite_le: null,
				dernier_renouvellement_le: null,
				dernier_rapport_le: null,
				derniere_erreur: null,
				contact: null,
				conditions_acceptees: null,
				conditions_en_vigueur: 1,
				peut_s_inscrire: true,
				essai_refuse: false,
				registre_url: 'https://reference.exemple.test',
			};
		if (chemin === '/api/admin/installation/conditions')
			return { version: 1, empreinte: 'abc', texte: TEXTE };
		return undefined;
	});
	await page.goto('/admin?onglet=installation');
	await page.getByRole('button', { name: 'Inscrire l’installation' }).click();

	const boite = page.getByRole('region', { name: 'Conditions d’inscription, version 1' });
	await expect(boite.locator('strong', { hasText: 'Version : 1' })).toBeVisible();
	await expect(boite.locator('blockquote')).toContainText('pas un avis juridique');
	//  Le `#` du texte n'est pas le titre de la page : il descend d'un étage (h4).
	await expect(boite.locator('h4')).toHaveText('Conditions d’inscription');
	await expect(boite.locator('h1')).toHaveCount(0);
	const lien = boite.getByRole('link', { name: 'licence' });
	await expect(lien).toHaveAttribute('href', 'https://exemple.test/LICENSE');
	await expect(lien).toHaveAttribute('target', '_blank');
	await expect(boite).not.toContainText('**');

	//  Le HTML glissé dans le texte est assaini : ni gestionnaire, ni script.
	await expect(boite.locator('script')).toHaveCount(0);
	await expect(boite.locator('[onerror]')).toHaveCount(0);
	expect(await page.evaluate(() => (window as { __xss?: number }).__xss)).toBeUndefined();

	//  La boîte défile : elle se parcourt au clavier.
	await expect(boite).toHaveAttribute('tabindex', '0');
});
