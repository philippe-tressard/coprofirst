/*
 *  **Le point CS / Syndic du Suivi des affaires** (#2041, maquettes A1 et C1).
 *
 *  Sur le VRAI écran, API simulée : ouvrir un point (quand, où, qui — un membre
 *  coché, un invité ajouté), puis saisir le compte rendu d'une affaire dans le
 *  tableau ; il paraît dans la ligne et dans le compte rendu global. Les règles
 *  (un point par mode, reprise, non traitées) sont tenues au serveur par
 *  `api/tests/test_points_conseil.py`.
 *
 *  #2082 : la saisie propose l'état à la validation (coché d'office par le
 *  serveur) et la case « CS et présents » ; 🔴 après « Enregistrer », l'affaire
 *  SUIVANTE se déplie et son titre se place en haut de l'écran.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';
import type { CompteRenduPoint, CrAffaire, ParticipantsPoint, SuiviAffaires } from '../src/lib/api';

const AFFAIRE = {
	id: 31,
	numero: 'TK-000031',
	titre: 'Interphone bâtiment C muet',
	descriptif: 'La platine de rue ne sonne plus.',
	categorie: 'panne',
	libelle_categorie: 'Panne',
	statut: 'en_cours',
	libelle_statut: 'Chez le syndic',
	ouverte_le: '2026-07-02',
	age_jours: 106,
	anciennete: 'ancienne' as const,
	perimetre_cible: [],
	jours_sans_avancee: 40,
	a_relancer: true,
	relances: [],
	apercu: 'La platine de rue ne sonne plus.',
	apercu_ia: false,
	batiments: [],
	etat_visite: null,
	a_evolue: false,
	motif_evolution: null,
	confidentiel: false,
	public_cible: [],
	reserve_perimetre: false,
	etat_par_defaut: 'en_cours',
	groupe: null,
	fusionnees: [],
};

/** Une seconde affaire, plus récente : la suivante du tableau. */
const SUIVANTE = {
	...AFFAIRE,
	id: 32,
	numero: 'TK-000032',
	titre: 'Fuite en toiture bâtiment A',
	ouverte_le: '2026-09-02',
	age_jours: 47,
	anciennete: 'moyenne' as const,
	confidentiel: false,
	public_cible: [],
	reserve_perimetre: false,
};

const RELEVE: SuiviAffaires = {
	jour: '2026-10-19',
	total: 1,
	anciennes: 1,
	fusionnees: 0,
	resumes_disponibles: false,
	delai_jours: 30,
	mode: 'affaires',
	par_categorie: [
		{
			cle: 'panne',
			libelle: 'Panne',
			nombre: 1,
			tranches: [{ cle: 'racine', libelle: 'Résidence', nombre: 1, teinte: 'p1' }],
		},
	],
	par_batiment: [],
	affaires: [AFFAIRE],
};

const ANNUAIRE: ParticipantsPoint = {
	conseil: [{ id: 3, prenom: 'Reine', nom: 'Martin', fonction: null }],
	syndic: [{ id: 7, prenom: 'Paul', nom: 'Bernard', fonction: 'Gestionnaire' }],
	lieux: [{ libelle: 'Résidence', adresse: '1 rue Test' }],
	moyens: [
		{ cle: 'sur_place', libelle: 'Sur place', avec_lieu: true },
		{ cle: 'visio', libelle: 'Visioconférence', avec_lieu: false },
		{ cle: 'telephone', libelle: 'Téléphone', avec_lieu: false },
		{ cle: 'hybride', libelle: 'Sur place et à distance', avec_lieu: true },
	],
	categories_seance: [{ cle: 'panne', libelle: 'Panne' }],
	etats_validation: [
		{ cle: 'en_cours', libelle: 'Chez le syndic' },
		{ cle: 'en_ag', libelle: 'À l’AG' },
		{ cle: 'résolu', libelle: 'Résolu' },
	],
};

function compteRendu(cr: CrAffaire | null): CompteRenduPoint {
	return {
		point: {
			id: 5,
			mode: 'affaires',
			etat: 'en_cours',
			debut: '2026-10-19T17:00:00',
			fin: null,
			moyen: 'sur_place',
			a_distance: false,
			lieu: '1 rue Test',
			ou: 'Sur place — 1 rue Test',
			cree_le: '2026-10-19T15:00:00',
			termine_le: null,
			valide_le: null,
			revision: 0,
			pdf_range: false,
		},
		presents: [
			{
				id: 1,
				nature: 'cs',
				membre_cs_id: 3,
				membre_syndic_id: null,
				prenom: 'Reine',
				nom: 'Martin',
				entreprise: null,
				fonction: null,
				telephone: null,
				email: null,
				destinataire: false,
				valide_le: null,
				par_derogation: false,
			},
			{
				id: 2,
				nature: 'invite',
				membre_cs_id: null,
				membre_syndic_id: null,
				prenom: 'Jean',
				nom: 'Durand',
				entreprise: 'Étanchéité Sud',
				fonction: null,
				telephone: null,
				email: null,
				destinataire: false,
				valide_le: null,
				par_derogation: false,
			},
		],
		abordees: cr
			? [{ affaire: { id: 31, numero: 'TK-000031', titre: AFFAIRE.titre }, cr, marque: null }]
			: [],
		non_traitees: cr ? [] : [{ id: 31, numero: 'TK-000031', titre: AFFAIRE.titre }],
		validation: { destinataires: 0, valides: 0, suspendue: false, echeance: null },
		commentaires: [],
		revision: 0,
	};
}

const CR: CrAffaire = {
	ticket_id: 31,
	contenu: '<p>Le syndic relance l’entreprise.</p>',
	brouillon: false,
	conseil_seul: false,
	etat_cible: 'en_cours',
	mis_a_jour_le: '2026-10-19T15:10:00',
};

test('ouvrir un point, puis saisir le compte rendu d’une affaire', async ({ page }) => {
	const envois: { quoi: string; corps: unknown }[] = [];
	page.on('request', (r) => {
		const url = new URL(r.url());
		if (url.pathname.startsWith('/api/points-conseil') && r.method() !== 'GET')
			envois.push({ quoi: `${r.method()} ${url.pathname}`, corps: r.postDataJSON() });
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/suivi-affaires') return RELEVE;
		if (chemin === '/api/points-conseil/participants') return ANNUAIRE;
		if (chemin === '/api/points-conseil') return compteRendu(null);
		if (chemin === '/api/points-conseil/5/affaires/31') return compteRendu(CR);
		return undefined;
	});
	await page.goto('/espace-cs/reporting');
	await attendreHydratation(page);

	await page.getByRole('button', { name: 'Ouvrir un point CS / Syndic' }).click();
	//  Le lieu proposé d'office est celui de la résidence.
	await expect(page.getByLabel('Lieu')).toHaveValue('1 rue Test');
	//  Les intitulés du Quand et du Où sont sur une même ligne (finition du
	//  17/10/2026 : la bascule « Sur place | À distance » décalait celui du lieu).
	if ((page.viewportSize()?.width ?? 0) >= 768) {
		const hauts = await Promise.all(
			['Début', 'Fin', 'Moyen', 'Lieu'].map(async (l) =>
				Math.round(
					(await page.locator('form.point-form label', { hasText: l }).first().boundingBox())?.y ??
						-1,
				),
			),
		);
		expect(new Set(hauts).size, `hauts des intitulés : ${hauts}`).toBe(1);
	}
	//  Sans personne sur place, pas de lieu ; il revient avec « Sur place ».
	await page.getByLabel('Moyen').selectOption('visio');
	await expect(page.getByLabel('Lieu')).toHaveCount(0);
	await page.getByLabel('Moyen').selectOption('sur_place');
	await expect(page.getByLabel('Lieu')).toHaveValue('1 rue Test');

	//  Une rangée par population, chacune nommée.
	for (const nom of ['Conseil syndical', 'Syndic', 'Invités'])
		await expect(page.getByRole('group', { name: nom, exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Reine MARTIN' }).click();
	//  Plusieurs invités, et chacun se retire par la croix des pastilles.
	for (const [prenom, entreprise] of [
		['Jean', 'Étanchéité Sud'],
		['Lise', 'Ascenseurs Test'],
	]) {
		await page.getByRole('button', { name: 'Ajouter un invité' }).click();
		await page.getByLabel('Prénom').fill(prenom);
		await page.getByLabel('Entreprise').fill(entreprise);
		await page
			.getByRole('group', { name: 'Ajouter un invité' })
			.getByRole('button', { name: 'Enregistrer' })
			.click();
	}
	const invites = page.getByRole('group', { name: 'Invités', exact: true });
	await expect(invites.locator('.pastille-retirable')).toHaveCount(2);
	await invites.getByRole('button', { name: 'Retirer Lise' }).click();
	await expect(invites.locator('.pastille-retirable')).toHaveText(['Étanchéité Sud Jean ×']);
	await page
		.locator('form.point-form > .form-actions')
		.getByRole('button', { name: 'Enregistrer' })
		.click();

	await expect.poll(() => envois.map((e) => e.quoi)).toContain('POST /api/points-conseil');
	const ouverture = envois.find((e) => e.quoi === 'POST /api/points-conseil')?.corps as {
		moyen: string;
		lieu: string | null;
		presents: { nature: string; membre_id?: number; entreprise?: string }[];
	};
	expect([ouverture.moyen, ouverture.lieu]).toEqual(['sur_place', '1 rue Test']);
	expect(ouverture.presents).toEqual([
		{ nature: 'cs', membre_id: 3 },
		expect.objectContaining({ nature: 'invite', prenom: 'Jean', entreprise: 'Étanchéité Sud' }),
	]);

	//  Le bandeau dit l'état et les présents ; le CR global, les non traitées.
	const point = page.locator('section.point');
	await expect(point).toContainText('En cours');
	await expect(point).toContainText('Reine MARTIN, Jean DURAND');
	await expect(page.getByRole('region', { name: 'Compte rendu du point' })).toContainText(
		'Non traitées · 1',
	);

	await page.getByRole('button', { name: 'Compte rendu' }).click();
	//  L'état à la validation, coché d'office par le serveur (#2082).
	await expect(page.getByLabel('État à la validation du compte rendu')).toHaveValue('en_cours');
	await expect(page.locator('.saisie-cr')).toContainText('CS et présents');
	const editeur = page.locator('.saisie-cr .tiptap');
	await editeur.click();
	await editeur.pressSequentially('Le syndic relance l’entreprise.');
	await page.locator('.saisie-cr').getByRole('button', { name: 'Enregistrer' }).click();

	await expect
		.poll(() => envois.map((e) => e.quoi))
		.toContain('PUT /api/points-conseil/5/affaires/31');
	await expect(page.locator('.saisie-cr')).toHaveCount(0);
	await expect(page.locator('table.affaires .cr')).toContainText('CR saisi');
	const global = page.getByRole('region', { name: 'Compte rendu du point' });
	await expect(global).toContainText('Les affaires abordées · 1');
	await expect(global).toContainText('Le syndic relance l’entreprise.');
	//  L'espace avant la précision d'un présent (v2.174.1) : « Durand(Étanchéité… » se lisait collé.
	await expect(global).toContainText('Jean DURAND (Étanchéité Sud)');
});

test('après « Enregistrer », l’affaire suivante se déplie, son titre en haut de l’écran', async ({
	page,
}) => {
	//  Une longue liste : sans défilement, la suivante resterait hors de l'écran.
	const remplissage = Array.from({ length: 12 }, (_, i) => ({
		...SUIVANTE,
		id: 100 + i,
		numero: `TK-0001${String(i).padStart(2, '0')}`,
		titre: `Affaire de remplissage ${i + 1}`,
	}));
	const releve = { ...RELEVE, total: 14, affaires: [AFFAIRE, ...remplissage, SUIVANTE] };
	//  La suivante de l'affaire 31 est la première de remplissage.
	const suivante = remplissage[0];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/suivi-affaires') return releve;
		if (chemin === '/api/points-conseil/participants') return ANNUAIRE;
		if (chemin === '/api/points-conseil/courant')
			return { compte_rendu: compteRendu(null), reprise: null };
		if (chemin === '/api/points-conseil/5/affaires/31') return compteRendu(CR);
		return undefined;
	});
	await page.goto('/espace-cs/reporting');
	await attendreHydratation(page);

	await page.locator('#affaire-31').getByRole('button', { name: 'Compte rendu' }).click();
	const editeur = page.locator('.saisie-cr .tiptap');
	await editeur.click();
	await editeur.pressSequentially('Relance faite.');
	await page.locator('.saisie-cr').getByRole('button', { name: 'Enregistrer' }).click();

	//  La suivante est ouverte, et elle seule.
	await expect(page.locator(`#saisie-cr-${suivante.id}`)).toBeVisible();
	await expect(page.locator('.saisie-cr')).toHaveCount(1);
	//  Son titre est en haut de l'écran, sous l'en-tête fixe : on n'a pas à la chercher.
	await expect
		.poll(async () => {
			const boite = await page.locator(`#affaire-${suivante.id}`).boundingBox();
			return boite ? Math.round(boite.y) : -1;
		})
		.toBeLessThan(120);
	await expect
		.poll(async () => {
			const boite = await page.locator(`#affaire-${suivante.id}`).boundingBox();
			return boite ? Math.round(boite.y) : -1;
		})
		.toBeGreaterThanOrEqual(0);
});

test('pendant le point, « Ouvrir une affaire en séance » la crée et l’ajoute (#2084)', async ({
	page,
}) => {
	const envois: { quoi: string; corps: unknown }[] = [];
	page.on('request', (r) => {
		const url = new URL(r.url());
		if (url.pathname === '/api/points-conseil/5/affaires')
			envois.push({ quoi: r.method(), corps: r.postDataJSON() });
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/suivi-affaires') return RELEVE;
		if (chemin === '/api/points-conseil/participants') return ANNUAIRE;
		if (chemin === '/api/points-conseil/courant')
			return { compte_rendu: compteRendu(null), reprise: null };
		if (chemin === '/api/points-conseil/5/affaires') return compteRendu(null);
		return undefined;
	});
	await page.goto('/espace-cs/reporting');
	await attendreHydratation(page);

	await page.getByRole('button', { name: 'Ouvrir une affaire en séance' }).click();
	await page.getByLabel('Titre de l’affaire').fill('Contrat ascenseur');
	await page.locator('#seance-categorie-5').selectOption('panne');
	await page.locator('.seance').getByRole('button', { name: 'Enregistrer' }).click();
	await expect.poll(() => envois.map((e) => e.quoi)).toContain('POST');
	expect(envois[0].corps).toEqual(
		expect.objectContaining({ titre: 'Contrat ascenseur', categorie: 'panne' }),
	);
});
