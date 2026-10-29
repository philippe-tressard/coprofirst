/*
 *  **Admin › Installations : le registre, vu de la référence (R4 #1880).**
 *
 *  Le VRAI onglet, API simulée. Ce que l'opérateur doit voir et pouvoir faire :
 *  - l'onglet n'existe que sur la RÉFÉRENCE — une réplique ne le montre pas ;
 *  - une carte par installation, son état teinté, le filtre qui compte ;
 *  - dépliée, la fiche : gestes possibles (dits par le serveur), services, contact,
 *    contrat archivé, journal ;
 *  - un geste demande un MOTIF, part au serveur, et la fiche rendue s'affiche ;
 *  - une installation RÉSILIÉE se supprime : motif, appel, et la carte quitte la liste ;
 *  - côté réplique, Admin › Services grise un service que la référence n'autorise pas ;
 *  - ses ALERTES (R4b #1960) : badge teinté de la plus sérieuse et noms sur la carte
 *    repliée, liste en tête de la fiche, les graves dites « courriel à l'opérateur » ;
 *  - le DERNIER RAPPORT : chaque point de conformité en coche — conforme, à corriger,
 *    inconnu (jamais ✓) —, une phrase qui dit le fait, l'explication au clavier.
 *  - le CANAL ET LA VERSION (#2210) : la version cible que le serveur calcule, le
 *    canal (Urgence ou une version publiée) et la vague réglés avec un motif — seules
 *    les vagues du canal retenu s'offrent —, et les versions publiées en tête.
 *  Sur bureau et sur téléphone, sans défilement horizontal.
 */
import { boiteStable, expect, MEMBRE_CS, simulerApi, test } from './aides';
import { attendreLisible, forcerTheme } from './contraste-ecran';
import type { FicheInstallation, RapportInstallation, RegistreLu } from '../src/lib/api';

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
	canal: 'urgence',
	version_logicielle: '2.144.1',
	cree_le: '2026-10-13T21:12:13',
	vue_le: '2026-10-13T21:12:13',
	administrateur: 'Alix DURAND',
	conditions_acceptees: 1,
	dernier_rapport_le: null,
	services_autorises: [],
	alertes: [],
	vague: 2,
	version_cible: null,
};

const ALERTES = [
	{
		code: 'muette',
		libelle: 'Installation muette',
		message: 'Aucun signe de vie depuis 72 h.',
		grave: true,
	},
	{
		code: 'disque_plein',
		libelle: 'Disque plein',
		message: 'Disque occupé à 91 %.',
		grave: false,
	},
];

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
	versions: {
		proposees: [
			{ version: '2.172.0', publiee_le: '2026-10-16T03:50:00' },
			{ version: '2.171.2', publiee_le: '2026-10-10T03:50:00' },
			{ version: '2.170.4', publiee_le: '2026-10-02T03:50:00' },
		],
		lues_le: '2026-10-17T03:50:00',
	},
	vagues: [
		{
			code: 0,
			libelle: 'Urgence',
			detail: 'la dernière version, aussitôt publiée',
			avec_urgence: true,
			defaut: false,
			cible: { version: '2.172.0', publiee_le: '2026-10-16T03:50:00' },
		},
		{
			code: 1,
			libelle: 'Pilote',
			detail: 'la dernière version publiée depuis 7 jours',
			avec_urgence: true,
			defaut: false,
			cible: { version: '2.171.2', publiee_le: '2026-10-10T03:50:00' },
		},
		{
			code: 2,
			libelle: 'Standard',
			detail: 'le dernier correctif de 7 jours de la mineure précédente (y-1)',
			avec_urgence: true,
			defaut: true,
			cible: { version: '2.171.2', publiee_le: '2026-10-10T03:50:00' },
		},
		{
			code: 3,
			libelle: 'Fixe',
			detail: 'la version choisie, 7 jours après sa publication',
			avec_urgence: false,
			defaut: false,
			cible: null,
		},
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

async function ouvrir(
	page,
	role: 'reference' | 'replique' = 'reference',
	alertes: typeof ALERTES = [],
	champsFiche: Partial<FicheInstallation> = {},
) {
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
		if (chemin === '/api/admin/installations')
			return {
				...REGISTRE,
				installations: REGISTRE.installations.map((i) =>
					i.identifiant === 'CF-000003' ? { ...i, alertes } : i,
				),
			};
		if (chemin === '/api/admin/installations/CF-000003') return fiche({ alertes, ...champsFiche });
		if (chemin === '/api/admin/installations/CF-000003/decisions')
			return fiche({ etat: 'active', gestes_possibles: ['suspendre', 'resilier'] });
		if (chemin === '/api/admin/installations/CF-000003/distribution')
			return fiche({
				...champsFiche,
				canal: '2.170.4',
				vague: 3,
				version_cible: '2.170.4',
			});
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
	//  La fenêtre de saisie garde sa marge intérieure : le champ et les boutons ne
	//  collent pas au bord (`Saisie` sans `.modal-body` — signalé le 14/10/2026).
	await expect(saisie.getByRole('textbox')).toBeVisible();
	const boite = await page.locator('.modal').boundingBox();
	for (const el of [saisie.getByRole('textbox'), saisie.getByRole('button', { name: 'Annuler' })]) {
		const b = await el.boundingBox();
		expect(b && boite && b.x - boite.x, 'marge gauche dans la fenêtre de saisie').toBeGreaterThan(
			8,
		);
	}
	await page.locator('.modal').screenshot({
		path: `test-results/saisie-${test.info().project.name}.png`,
	});
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

test('Installations : les alertes se lisent sur la carte et en tête de la fiche', async ({
	page,
}) => {
	await ouvrir(page, 'reference', ALERTES);
	const carte = page.locator('#installation-CF-000003');
	//  Repliée : le badge compte, la plus sérieuse le teinte, et les noms se lisent
	//  sans survol — au doigt, il n'y en a pas.
	const badge = carte.locator('.badge', { hasText: '2 alertes' });
	await expect(badge).toBeVisible();
	await expect(badge).toHaveClass(/badge-red/);
	await expect(carte.getByText('Installation muette · Disque plein')).toBeVisible();
	await expect(
		page.locator('#installation-CF-000000').locator('.badge', { hasText: /alerte/ }),
	).toHaveCount(0);

	await carte.getByRole('button', { name: /CF-000003/ }).click();
	const liste = carte.locator('.alertes li');
	await expect(liste).toHaveCount(2);
	await expect(liste.nth(0)).toContainText('Aucun signe de vie depuis 72 h.');
	await expect(liste.nth(0)).toContainText('courriel à l’opérateur');
	await expect(liste.nth(1)).not.toContainText('courriel à l’opérateur');
	//  Les alertes passent avant la décision : c'est elles qui l'appellent.
	await expect(carte.locator('h4.intertitre').nth(0)).toHaveText('Alertes');
	await expect(carte.locator('h4.intertitre').nth(1)).toHaveText('Décision');

	await carte.screenshot({ path: `test-results/registre-alertes-${test.info().project.name}.png` });
	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'défilement horizontal dans l’onglet Installations').toBe(false);
});

test('Installations : une installation résiliée se supprime, et quitte la liste', async ({
	page,
}) => {
	const ecrits = await ouvrir(page, 'reference', [], {
		etat: 'resiliee',
		gestes_possibles: ['supprimer'],
	});
	const carte = page.locator('#installation-CF-000003');
	await carte.getByRole('button', { name: /CF-000003/ }).click();
	await expect(carte.getByText(/seul le contrat accepté reste archivé/)).toBeVisible();
	await carte.getByRole('button', { name: /Supprimer/ }).click();
	const saisie = page.getByRole('dialog');
	await expect(saisie.getByText(/reste archivé cinq ans/)).toBeVisible();
	await saisie.getByRole('textbox').fill('installation d’essai');
	await saisie.getByRole('button', { name: 'Supprimer' }).click();
	await expect(carte).toHaveCount(0);
	await expect(page.locator('#installation-CF-000000')).toBeVisible();
	expect(ecrits).toEqual([
		{
			methode: 'POST',
			chemin: '/api/admin/installations/CF-000003/suppression',
			corps: { motif: 'installation d’essai' },
		},
	]);
});

/**  Un rapport nocturne : chaque point de conformité dans un état choisi. */
function rapport(
	posture: RapportInstallation['posture'],
	copie_hors_machine: boolean | null,
): RapportInstallation {
	return {
		identite: { version_logicielle: '2.156.0', revision_base: null, derniere_mise_a_jour: null },
		hebergement: {
			hebergeur: null,
			pays_donnees: 'FR',
			architecture: 'aarch64',
			memoire_mo: 8000,
			disque_total_mo: 100000,
			disque_occupe_mo: 20000,
			moteur_base: 'postgresql',
			taille_bases_mo: 40,
			certificat_expire_le: null,
		},
		sauvegarde: {
			derniere_reussie_le: '2026-10-15T02:00:00',
			copie_hors_machine,
			dernier_essai_restauration_le: null,
		},
		posture,
		coproprietes: [],
	};
}

test('Installations : la posture se lit en coches — conforme, à corriger, inconnu', async ({
	page,
}) => {
	await ouvrir(page, 'reference', [], {
		dernier_rapport_le: '2026-10-15T03:00:00',
		dernier_rapport: rapport(
			{
				documentation_api_coupee: true,
				cookie_securise: false,
				secret_suffisant: null,
				lien_source_present: true,
			},
			null,
		),
	});
	const carte = page.locator('#installation-CF-000003');
	await carte.getByRole('button', { name: /CF-000003/ }).click();

	//  🔴 L'état SAIN de la documentation d'API se dit « non publiée » : « coupée :
	//  oui » se lisait comme une panne, et « publiée ✓ » dirait l'inverse du fait.
	const doc = carte.getByRole('button', { name: 'Documentation d’API non publiée — Conforme' });
	await expect(doc).toBeVisible();
	await expect(doc.locator('[data-etat]')).toHaveAttribute('data-etat', 'conforme');
	await expect(carte.getByText(/coupée/)).toHaveCount(0);

	const cookie = carte.getByRole('button', { name: 'Cookie de session non sécurisé — À corriger' });
	await expect(cookie.locator('[data-etat]')).toHaveAttribute('data-etat', 'a-corriger');

	//  INCONNU n'est jamais ✓ : la mesure qui n'a pas pu se faire n'atteste rien.
	for (const nom of ['Clé secrète — Inconnu', 'Copie hors machine — Inconnu']) {
		const inconnu = carte.getByRole('button', { name: nom });
		await expect(inconnu.locator('[data-etat]')).toHaveAttribute('data-etat', 'inconnu');
		await expect(inconnu.locator('svg')).toHaveCount(0);
	}

	//  L'explication s'ouvre au CLAVIER (et au toucher) — pas seulement au survol.
	//  ⚠️ La capture d'un élément fait DÉFILER la page, et la bulle se ferme au
	//  défilement (`ux-patterns` §17) : la carte se prend avant, la bulle ensuite,
	//  sur l'écran tel qu'il est.
	await carte.screenshot({ path: `test-results/registre-posture-${test.info().project.name}.png` });
	const bulle = page.locator(`#${await doc.getAttribute('aria-controls')}`);
	await expect(bulle).toBeHidden();
	await doc.focus();
	//  La carte dépliée cale la page en défilant, et la bulle se ferme au défilement :
	//  sur une fiche plus haute (la section « Canal et version », #1881), Entrée
	//  tombait encore dans ce défilement — deux échecs sur trois. On attend l'arrêt.
	await boiteStable(doc);
	await page.keyboard.press('Enter');
	await expect(doc).toHaveAttribute('aria-expanded', 'true');
	await expect(bulle).toBeVisible();
	await expect(bulle).toContainText('/docs, /redoc et /openapi.json');
	await bulle.evaluate((e) => Promise.all(e.getAnimations().map((a) => a.finished)));
	await page.screenshot({ path: `test-results/registre-bulle-${test.info().project.name}.png` });
	await page.keyboard.press('Escape');
	await expect(bulle).toBeHidden();
	await expect(doc).toBeFocused();

	//  Une bulle ouverte ne déborde pas de l'écran, même pour le dernier point.
	const dernier = carte.getByRole('button', { name: /Lien vers le code source/ });
	await dernier.click();
	const sienne = page.locator(`#${await dernier.getAttribute('aria-controls')}`);
	await expect(sienne).toBeVisible();
	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'défilement horizontal avec une bulle ouverte').toBe(false);
	//  Un clic ailleurs la ferme — par la souris, sans défiler : un `click()` de
	//  Playwright ferait défiler, et la bulle se fermerait pour une autre raison.
	const ailleurs = await carte.locator('dt', { hasText: 'Posture' }).boundingBox();
	if (!ailleurs) throw new Error('libellé « Posture » introuvable');
	await page.mouse.click(ailleurs.x + 4, ailleurs.y + ailleurs.height / 2);
	await expect(sienne).toBeHidden();
});

test('Installations : une documentation d’API publiée est à corriger', async ({ page }) => {
	await ouvrir(page, 'reference', [], {
		dernier_rapport_le: '2026-10-15T03:00:00',
		dernier_rapport: rapport(
			{
				documentation_api_coupee: false,
				cookie_securise: true,
				secret_suffisant: true,
				lien_source_present: true,
			},
			true,
		),
	});
	const carte = page.locator('#installation-CF-000003');
	await carte.getByRole('button', { name: /CF-000003/ }).click();
	const doc = carte.getByRole('button', { name: 'Documentation d’API publiée — À corriger' });
	await expect(doc.locator('[data-etat]')).toHaveAttribute('data-etat', 'a-corriger');
	await expect(
		carte.getByRole('button', { name: 'Copie hors machine — Conforme' }).locator('[data-etat]'),
	).toHaveAttribute('data-etat', 'conforme');
});

test('Installations : le canal et la version — la vague, la version fixée, et la cible du bail', async ({
	page,
}) => {
	const ecrits = await ouvrir(page, 'reference', [], {
		etat: 'active',
		version_cible: '2.172.0',
		gestes_possibles: ['suspendre', 'resilier'],
	});
	//  Les versions publiées, en tête de l'onglet : ce que chaque vague installe.
	await page.getByRole('button', { name: /Versions publiées/ }).click();
	const publiees = page.locator('.cibles');
	await expect(publiees.getByText('Urgence', { exact: true })).toBeVisible();
	await expect(publiees.locator('li', { hasText: 'Standard' })).toContainText('v2.171.2');

	const carte = page.locator('#installation-CF-000003');
	await carte.getByRole('button', { name: /CF-000003/ }).click();
	await expect(carte.locator('h4.intertitre', { hasText: 'Canal et version' })).toBeVisible();
	await expect(carte.getByText('Version cible du prochain bail :')).toContainText('v2.172.0');

	//  Canal Urgence : Urgence, Pilote et Standard s'offrent, pas Fixe.
	await expect(carte.getByRole('radio', { name: /Standard/ })).toBeChecked();
	await expect(carte.getByRole('radio', { name: /Fixe/ })).toHaveCount(0);
	//  Une version choisie : seule Fixe s'offre, et elle est retenue.
	await carte.getByLabel('Canal suivi').selectOption('2.170.4');
	await expect(carte.getByRole('radio', { name: /Urgence/ })).toHaveCount(0);
	await expect(carte.getByRole('radio', { name: /Fixe/ })).toBeChecked();
	await carte.getByRole('button', { name: 'Enregistrer' }).click();
	const saisie = page.getByRole('dialog');
	await saisie.getByRole('textbox').fill('régression du 2.172');
	await saisie.getByRole('button', { name: 'Enregistrer' }).click();
	await expect(carte.getByText('Version cible du prochain bail :')).toContainText('v2.170.4');
	expect(ecrits).toEqual([
		{
			methode: 'PUT',
			chemin: '/api/admin/installations/CF-000003/distribution',
			corps: { canal: '2.170.4', vague: 3, motif: 'régression du 2.172' },
		},
	]);

	await carte.screenshot({ path: `test-results/registre-canal-${test.info().project.name}.png` });
	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'défilement horizontal dans l’onglet Installations').toBe(false);
});

test('@sombre — Installations : la liste et une fiche dépliée se lit au thème sombre', async ({
	page,
}) => {
	await ouvrir(page);
	const carte = page.locator('#installation-CF-000003');
	await carte.getByRole('button', { name: /CF-000003/ }).click();
	await expect(carte.getByText(/Version 1, acceptée le/)).toBeVisible();
	await forcerTheme(page, 'sombre');
	await attendreLisible(page, '#contenu');
});
