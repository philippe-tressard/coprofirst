/*
 *  **Admin › Installations : le registre, vu de la référence (R4 #1880).**
 *
 *  Le VRAI onglet, API simulée. Ce que l'opérateur doit voir et pouvoir faire :
 *  - l'onglet n'existe que sur la RÉFÉRENCE — une réplique ne le montre pas ;
 *  - une carte par installation, son état teinté, le filtre qui compte ;
 *  - dépliée, la fiche : gestes possibles (dits par le serveur), services, contact,
 *    contrat archivé, journal ;
 *  - un geste demande un MOTIF, part au serveur, et la fiche rendue s'affiche ;
 *  - côté réplique, Admin › Services grise un service que la référence n'autorise pas.
 *  Sur bureau et sur téléphone, sans défilement horizontal.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';
import type { FicheInstallation, RegistreLu } from '../src/lib/api';

const OPERATEUR = { ...MEMBRE_CS, role: 'admin', roles: ['admin', 'operateur'] };

const INSTALLATION = {
	empreinte: '79ce8c5b',
	demarree_le: '2026-10-13T19:39:00',
	retard: 0,
	libelle: 'Référence',
	branche: 'main',
	verification_active: false,
	etat: 'non_verifie',
	detail: '',
};

const DEMO = {
	identifiant: 'CF-000003',
	etat: 'en_attente' as const,
	canal: 'replica',
	version_logicielle: '2.144.1',
	cree_le: '2026-10-13T21:12:13',
	vue_le: '2026-10-13T21:12:13',
	administrateur: 'Alix DURAND',
	conditions_acceptees: 1,
	dernier_rapport_le: null,
	services_autorises: [],
};

const REGISTRE: RegistreLu = {
	actif: true,
	installations: [
		{
			...DEMO,
			identifiant: 'CF-000000',
			etat: 'active',
			canal: 'main',
			administrateur: null,
			conditions_acceptees: null,
		},
		DEMO,
	],
	services_accordables: [
		{ code: 'assistant_ia', libelle: 'Assistant IA' },
		{ code: 'diffusion', libelle: 'Diffusion sur le groupe WhatsApp' },
		{ code: 'reponses_courriel', libelle: 'Réponses par courriel' },
	],
};

function fiche(champs: Partial<FicheInstallation> = {}): FicheInstallation {
	return {
		...DEMO,
		contact: {
			prenom: 'Alix',
			nom: 'Durand',
			courriel: 'alix@example.org',
			telephone: null,
			mis_a_jour_le: '2026-10-13T21:12:13',
		},
		contrats: [
			{
				version: 1,
				empreinte: 'b203d53e0792f715aa',
				texte: "# Conditions d'inscription\n\nLe texte exact accepté.",
				accepte_par: 'Alix DURAND <alix@example.org>',
				accepte_le: '2026-10-13T21:12:13',
			},
		],
		decisions: [
			{
				geste: 'conditions_acceptees',
				motif: 'conditions v1 acceptées',
				auteur: 'système',
				cree_le: '2026-10-13T21:12:13',
			},
			{ geste: 'inscription', motif: '', auteur: 'système', cree_le: '2026-10-13T21:12:13' },
		],
		dernier_rapport: null,
		gestes_possibles: ['valider', 'resilier'],
		services_modifiables: true,
		...champs,
	};
}

async function ouvrir(page, role: 'reference' | 'replique' = 'reference') {
	const ecrits: { methode: string; chemin: string; corps: unknown }[] = [];
	page.on('request', (r) => {
		const chemin = new URL(r.url()).pathname;
		if (r.method() !== 'GET' && chemin.startsWith('/api/admin/installations/')) {
			ecrits.push({ methode: r.method(), chemin, corps: r.postDataJSON() });
		}
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return OPERATEUR;
		if (chemin === '/api/admin/installation') return { ...INSTALLATION, role };
		if (chemin === '/api/admin/installations') return REGISTRE;
		if (chemin === '/api/admin/installations/CF-000003') return fiche();
		if (chemin === '/api/admin/installations/CF-000003/decisions')
			return fiche({ etat: 'active', gestes_possibles: ['suspendre', 'resilier'] });
		return undefined;
	});
	await page.goto('/admin?onglet=installations');
	return ecrits;
}

test('Installations : la carte, la fiche, et un geste motivé', async ({ page }) => {
	const ecrits = await ouvrir(page);
	const onglet = page.getByRole('link', { name: /Installations/ });
	await expect(onglet).toBeVisible();

	const carte = page.locator('#installation-CF-000003');
	await expect(carte).toBeVisible();
	await expect(carte.getByText('En attente', { exact: true })).toBeVisible();
	await expect(page.locator('#installation-CF-000000')).toBeVisible();

	await carte.getByRole('button', { name: /CF-000003/ }).click();
	await expect(carte.getByRole('link', { name: 'alix@example.org' })).toBeVisible();
	await expect(carte.getByText(/Version 1, acceptée le/)).toBeVisible();
	await expect(carte.getByRole('checkbox', { name: 'Assistant IA' })).not.toBeChecked();
	await expect(carte.getByRole('button', { name: /Rétablir/ })).toHaveCount(0);

	await page.evaluate(() => window.scrollTo(0, 0));
	await carte.screenshot({ path: `test-results/registre-${test.info().project.name}.png` });

	await carte.getByRole('button', { name: /Valider/ }).click();
	const saisie = page.getByRole('dialog');
	await saisie.getByRole('textbox').fill('inscription vérifiée');
	await saisie.getByRole('button', { name: 'Valider' }).click();
	await expect(carte.getByText('Active', { exact: true })).toBeVisible();
	await expect(carte.getByRole('button', { name: /Suspendre/ })).toBeVisible();
	expect(ecrits).toEqual([
		{
			methode: 'POST',
			chemin: '/api/admin/installations/CF-000003/decisions',
			corps: { geste: 'valider', motif: 'inscription vérifiée' },
		},
	]);

	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'défilement horizontal dans l’onglet Installations').toBe(false);
});

test('Installations : une réplique ne montre pas l’onglet', async ({ page }) => {
	await ouvrir(page, 'replique');
	await expect(page.getByRole('link', { name: /Maintenance/ })).toBeVisible();
	await expect(page.getByRole('link', { name: /^Installations$/ })).toHaveCount(0);
});
